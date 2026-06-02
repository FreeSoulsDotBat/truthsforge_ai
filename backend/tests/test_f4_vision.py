"""F4 — image-to-model: gateway multimodal + análise vision real.

Cobre, sem provedor real:
* os builders de bloco multimodal por provedor (`llm_gateway.multimodal`);
* o `_call_vision` real do analyzer: monta mensagem com imagem, coleta a
  descrição via `stream_chat`, e cai em metadata-only quando não há modelo
  vision ou a chamada falha.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.contracts import (
    ModelCapability,
    ModelConfig,
    ModelingPlanCreate,
    PlatformFile,
    ProviderName,
)
from app.llm_gateway.multimodal import (
    image_block,
    media_type_for,
    supports_image_blocks,
    text_block,
    user_message_with_images,
)
from app.llm_gateway.providers import ProviderStreamEvent
from app.modeling.attachment_analyzer import ModelingAttachmentAnalyzer

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-payload"


# ---------------------------------------------------------------------------
# multimodal builders (puros)
# ---------------------------------------------------------------------------


def test_media_type_for_by_suffix() -> None:
    assert media_type_for("ref.png") == "image/png"
    assert media_type_for("ref.JPG") == "image/jpeg"
    assert media_type_for("ref.jpeg") == "image/jpeg"
    assert media_type_for("ref.webp") == "image/webp"
    assert media_type_for(None) == "image/png"  # fallback


def test_supports_image_blocks_scopes_providers() -> None:
    assert supports_image_blocks(ProviderName.anthropic)
    assert supports_image_blocks(ProviderName.openai)
    # Google fica no caminho text-only (serialização de parts diferente).
    assert not supports_image_blocks(ProviderName.google)


def test_image_block_anthropic_shape() -> None:
    block = image_block(ProviderName.anthropic, PNG_BYTES, media_type="image/png")
    assert block["type"] == "image"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "image/png"
    assert block["source"]["data"]  # base64 não vazio


def test_image_block_openai_shape() -> None:
    block = image_block(ProviderName.openai, PNG_BYTES, media_type="image/jpeg")
    assert block["type"] == "input_image"
    assert block["image_url"].startswith("data:image/jpeg;base64,")


def test_text_block_per_provider() -> None:
    assert text_block(ProviderName.openai, "oi") == {"type": "input_text", "text": "oi"}
    assert text_block(ProviderName.anthropic, "oi") == {"type": "text", "text": "oi"}


def test_user_message_with_images_builds_blocks() -> None:
    msg = user_message_with_images(ProviderName.anthropic, "descreva", [(PNG_BYTES, "image/png")])
    assert msg["role"] == "user"
    assert isinstance(msg["content"], list)
    kinds = [b.get("type") for b in msg["content"]]
    assert kinds == ["text", "image"]


def test_user_message_text_only_without_images() -> None:
    msg = user_message_with_images(ProviderName.anthropic, "só texto", [])
    assert msg["content"] == "só texto"  # str, caminho text-only intacto


def test_user_message_text_only_for_unsupported_provider() -> None:
    # Google: mesmo com imagem, cai em text-only (sem quebrar o provider).
    msg = user_message_with_images(ProviderName.google, "descreva", [(PNG_BYTES, "image/png")])
    assert msg["content"] == "descreva"


# ---------------------------------------------------------------------------
# test doubles do analyzer
# ---------------------------------------------------------------------------


@dataclass
class _FakeStore:
    files: dict[str, PlatformFile] = field(default_factory=dict)
    models: list[ModelConfig] = field(default_factory=list)

    def get_platform_file(self, file_id: str) -> PlatformFile | None:
        return self.files.get(file_id)

    def list_models(self) -> list[ModelConfig]:
        return self.models


class _FakeVisionGateway:
    """Gateway que registra a mensagem recebida e devolve uma descrição."""

    def __init__(self, text: str = "Descrição da peça.", *, boom: bool = False) -> None:
        self._text = text
        self._boom = boom
        self.received_messages: list[dict[str, Any]] | None = None
        self.received_model: ModelConfig | None = None

    async def stream_chat(
        self,
        model: ModelConfig,
        messages: list[dict[str, Any]],
        reasoning_summary: str = "off",
    ) -> AsyncIterator[ProviderStreamEvent]:
        self.received_model = model
        self.received_messages = messages
        if self._boom:
            raise RuntimeError("provider exploded")
        mid = len(self._text) // 2
        for chunk in (self._text[:mid], self._text[mid:]):
            yield ProviderStreamEvent(kind="token", content=chunk)


def _vision_model() -> ModelConfig:
    return ModelConfig(
        id="claude-vision",
        provider=ProviderName.anthropic,
        display_name="Claude Vision",
        provider_model_id="claude-opus-4-8",
        capabilities=[ModelCapability.chat, ModelCapability.vision],
        default=True,
    )


def _image_file(tmp_path: Path) -> PlatformFile:
    storage = tmp_path / "ref.png"
    storage.write_bytes(PNG_BYTES)
    pf = PlatformFile(
        filename="ref.png",
        original_filename="ref.png",
        content_type="image/png",
        size_bytes=len(PNG_BYTES),
        storage_path=str(storage),
        source="chat_attachment",
    )
    return pf


# ---------------------------------------------------------------------------
# _call_vision / _analyze_image
# ---------------------------------------------------------------------------


def test_call_vision_sends_image_and_returns_description(tmp_path: Path) -> None:
    store = _FakeStore(models=[_vision_model()])
    gateway = _FakeVisionGateway("Caixa com tampa articulada por knuckles.")
    analyzer = ModelingAttachmentAnalyzer(store=store, gateway=gateway)  # type: ignore[arg-type]

    summary = analyzer._call_vision(PNG_BYTES, _image_file(tmp_path))

    assert summary == "Caixa com tampa articulada por knuckles."
    # mensagem multimodal: a última msg é user com bloco de imagem.
    assert gateway.received_messages is not None
    user_msg = gateway.received_messages[-1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert any(b.get("type") == "image" for b in user_msg["content"])
    assert gateway.received_model is not None
    assert gateway.received_model.provider == ProviderName.anthropic


def test_analyze_image_uses_vision_summary(tmp_path: Path) -> None:
    pf = _image_file(tmp_path)
    store = _FakeStore(files={pf.id: pf}, models=[_vision_model()])
    gateway = _FakeVisionGateway("Suporte de monitor em L com furos M4.")
    analyzer = ModelingAttachmentAnalyzer(store=store, gateway=gateway)  # type: ignore[arg-type]

    analysis = analyzer.analyze(pf.id)

    assert analysis.ok
    assert analysis.kind == "image"
    assert "Suporte de monitor" in analysis.summary


def test_call_vision_returns_none_without_vision_model(tmp_path: Path) -> None:
    # Loja sem modelos => sem vision => metadata-only.
    store = _FakeStore(models=[])
    gateway = _FakeVisionGateway()
    analyzer = ModelingAttachmentAnalyzer(store=store, gateway=gateway)  # type: ignore[arg-type]

    assert analyzer._call_vision(PNG_BYTES, _image_file(tmp_path)) is None
    # nada foi enviado ao gateway.
    assert gateway.received_messages is None


def test_call_vision_swallows_gateway_error(tmp_path: Path) -> None:
    store = _FakeStore(models=[_vision_model()])
    gateway = _FakeVisionGateway(boom=True)
    analyzer = ModelingAttachmentAnalyzer(store=store, gateway=gateway)  # type: ignore[arg-type]

    # Falha do provider não vaza: vira None (caller usa metadata-only).
    assert analyzer._call_vision(PNG_BYTES, _image_file(tmp_path)) is None


def test_build_attachments_context_renders_block(tmp_path: Path) -> None:
    """F4 wiring: o bloco <anexos-analisados> é montado a partir da análise —
    é o que a descoberta E o planejamento passam a injetar no prompt."""
    from app.modeling.planner_service import build_attachments_context

    pf = _image_file(tmp_path)
    store = _FakeStore(files={pf.id: pf}, models=[_vision_model()])
    gateway = _FakeVisionGateway("Caixa com tampa por knuckles e furos M4.")

    block = build_attachments_context(store, [pf.id], gateway=gateway)  # type: ignore[arg-type]

    assert block is not None
    assert "<anexos-analisados>" in block and "</anexos-analisados>" in block
    assert "Caixa com tampa por knuckles" in block


def test_build_attachments_context_none_without_files() -> None:
    from app.modeling.planner_service import build_attachments_context

    assert build_attachments_context(_FakeStore(), []) is None
    assert build_attachments_context(_FakeStore(), [""]) is None


def test_planner_service_injects_attachment_context(tmp_path: Path) -> None:
    """O planner passa a "ver" a imagem: _with_attachment_context analisa o
    anexo e injeta a descrição no prompt (gate F4 — antes a imagem sumia)."""
    from app.modeling.planner_service import ModelingPlannerService

    pf = _image_file(tmp_path)
    store = _FakeStore(files={pf.id: pf}, models=[_vision_model()])
    gateway = _FakeVisionGateway("Peça em L com 4 furos M4.")
    svc = ModelingPlannerService(store=store, gateway=gateway)  # type: ignore[arg-type]

    payload = ModelingPlanCreate(prompt="modele isso", attached_file_ids=[pf.id])
    out = svc._with_attachment_context(payload)

    assert out.prompt.startswith("modele isso")
    assert "<anexos-analisados>" in out.prompt
    assert "Peça em L com 4 furos M4." in out.prompt

    # Sem anexo, o payload passa intacto (mesma instância).
    plain = ModelingPlanCreate(prompt="oi")
    assert svc._with_attachment_context(plain) is plain


def test_explicit_vision_model_overrides_store(tmp_path: Path) -> None:
    store = _FakeStore(models=[])  # loja vazia
    gateway = _FakeVisionGateway("ok")
    analyzer = ModelingAttachmentAnalyzer(
        store=store,
        gateway=gateway,  # type: ignore[arg-type]
        vision_model=_vision_model(),
    )
    assert analyzer._call_vision(PNG_BYTES, _image_file(tmp_path)) == "ok"
