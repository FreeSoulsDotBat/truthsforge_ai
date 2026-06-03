"""Deep-analysis of chat attachments for 3D modeling discovery (Onda 2.6).

ADR-013 requires the discovery phase to consume images and 3D files
uploaded by the user so the agent can ground its plan in real data
instead of guesses. This module implements both paths:

* **Images** (``image/*``) — sent to the configured vision-capable LLM
  via the existing gateway. The provider receives the image as a
  base64-encoded data URL along with a Portuguese prompt asking for a
  geometry/material/process summary.
* **3D meshes** (``.stl``, ``.obj``, ``.3mf``, ``.blend``) — analysed
  headlessly through the Blender adapter using the allowlisted
  ``blender.validate_printability`` + ``blender.measure_object`` tools.
* **3D CAD** (``.step``) — Fusion adapter when available, otherwise
  metadata-only fallback.

Defensive guarantees:

* hard size limit (default 50 MB) before doing any heavy work;
* short per-call timeout (default 15 s);
* every exception path falls back to a minimal metadata-only analysis so
  the chat never crashes because an analysis failed.

The :class:`ModelingChatOrchestrator` (Onda 2.4) is the only direct
caller of this service; the HTTP endpoint added in Onda 2.7 simply
forwards to it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

from app.core.contracts import (
    ModelCapability,
    ModelConfig,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    PlatformFile,
)
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.multimodal import media_type_for, user_message_with_images
from app.modeling.blender_adapter import BlenderAdapter

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _run_coro(coro: Coroutine[Any, Any, _T]) -> _T:
    """Executa uma corrotina de forma síncrona, em qualquer contexto.

    O analyzer é chamado tanto de rotas síncronas quanto de dentro do
    orchestrator assíncrono. ``asyncio.run`` quebra se já houver loop ativo,
    então, nesse caso, rodamos a corrotina numa thread dedicada.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


# Prompt da análise vision (F4): descrição estruturada que aterra o planner.
_VISION_SYSTEM = (
    "Você é um engenheiro de CAD analisando uma imagem de referência para "
    "modelagem 3D paramétrica (sólidos mecânicos). Seja objetivo e técnico."
)
_VISION_PROMPT = (
    "Descreva a peça da imagem para reproduzi-la em CAD. Responda em PT-BR, "
    "em tópicos curtos:\n"
    "1. O que é a peça (função provável).\n"
    "2. Forma geral em primitivas reconhecíveis (caixa, cilindro, placa, "
    "revolução) e como se compõem.\n"
    "3. Proporções relativas (a imagem não dá escala — descreva razões, ex.: "
    "'altura ~2x a largura').\n"
    "4. Features mecânicas visíveis: furos, roscas, dobradiças/knuckles, "
    "encaixes, chanfros, nervuras, padrões.\n"
    "5. Esboço de um plano de modelagem (ordem de operações).\n"
    "Não invente dimensões absolutas em mm; deixe claro o que precisa ser "
    "confirmado com o usuário."
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_TIMEOUT_SECONDS = 15

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
MESH_EXTENSIONS = frozenset({".stl", ".obj", ".3mf"})
BLEND_EXTENSIONS = frozenset({".blend"})
CAD_EXTENSIONS = frozenset({".step", ".stp"})

AttachmentKind = Literal[
    "image",
    "mesh",
    "blend",
    "cad",
    "unsupported",
]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AttachmentAnalysis:
    """Outcome of analysing a single attachment for the modeling agent."""

    file_id: str
    filename: str
    kind: AttachmentKind
    ok: bool
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    error: str | None = None

    def to_context_text(self) -> str:
        """Render the analysis into a single block the agent can read.

        Used by the chat-stream handler to feed the analysis back into
        the LLM as additional context (system or assistant message).
        """

        lines = [
            f"Anexo {self.filename} ({self.kind})",
            self.summary if self.summary else "Sem resumo disponível.",
        ]
        if self.metrics:
            metric_lines = ", ".join(
                f"{key}={value}" for key, value in sorted(self.metrics.items())
            )
            lines.append(f"Métricas: {metric_lines}")
        if self.suggestions:
            for hint in self.suggestions:
                lines.append(f"- {hint}")
        if not self.ok and self.error:
            lines.append(f"Falha de análise: {self.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class ModelingAttachmentAnalyzer:
    """Inspect chat attachments and return a structured analysis."""

    def __init__(
        self,
        store: Any,
        gateway: LLMGateway | None = None,
        blender: BlenderAdapter | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        vision_model: ModelConfig | None = None,
    ) -> None:
        self.store = store
        self.gateway = gateway or LLMGateway()
        self._vision_model = vision_model
        self.blender = blender or BlenderAdapter(timeout_seconds=timeout_seconds)
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def analyze(self, file_id: str) -> AttachmentAnalysis:
        """Resolve ``file_id`` and run the appropriate analysis.

        Always returns an :class:`AttachmentAnalysis` — exceptions are
        captured and surfaced as ``ok=False`` results so the chat flow
        never breaks because of a malformed attachment.
        """

        platform_file = self._load_file(file_id)
        if platform_file is None:
            return AttachmentAnalysis(
                file_id=file_id,
                filename="<desconhecido>",
                kind="unsupported",
                ok=False,
                summary="Arquivo não encontrado na biblioteca.",
                error="platform_file_not_found",
            )

        kind = classify_attachment(platform_file)
        if not self._is_within_size_limit(platform_file):
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary=(
                    f"Arquivo excede o limite de {self.max_bytes // (1024 * 1024)} MB para análise."
                ),
                error="attachment_too_large",
            )

        path = Path(platform_file.storage_path)
        if not path.is_file():
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary="Conteúdo do arquivo indisponível no disco.",
                error="storage_path_missing",
            )

        # Reverifica contra o tamanho REAL no disco: ``size_bytes`` pode vir 0/None
        # (desconhecido) e burlar ``_is_within_size_limit``, levando a uma leitura
        # pesada de um arquivo grande. Esta é a barreira efetiva antes do trabalho.
        try:
            real_size = path.stat().st_size
        except OSError:
            real_size = 0
        if real_size > self.max_bytes:
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary=(
                    f"Arquivo excede o limite de {self.max_bytes // (1024 * 1024)} MB para análise."
                ),
                error="attachment_too_large",
            )

        try:
            if kind == "image":
                return self._analyze_image(platform_file, path)
            if kind in {"mesh", "blend"}:
                return self._analyze_mesh(platform_file, path, kind=kind)
            if kind == "cad":
                return self._analyze_cad_metadata(platform_file, path)
        except Exception as exc:  # noqa: BLE001 - defensive: never crash chat
            logger.exception("Attachment analysis failed for %s", file_id)
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary="Falha inesperada ao analisar o anexo.",
                error=str(exc),
            )

        return AttachmentAnalysis(
            file_id=file_id,
            filename=platform_file.filename,
            kind="unsupported",
            ok=False,
            summary="Tipo de anexo ainda não é suportado pela análise de modelagem.",
            error="unsupported_attachment_kind",
        )

    # ------------------------------------------------------------------
    # internals — image
    # ------------------------------------------------------------------

    def _analyze_image(self, platform_file: PlatformFile, path: Path) -> AttachmentAnalysis:
        """Send the image to the vision-capable LLM via the gateway (F4).

        Builds a multimodal message (text + image block in the chosen
        provider's format) and asks for a structured CAD description that
        grounds the planner. When no vision model is configured the call
        returns ``None`` and we fall back to a metadata-only summary so the
        agent still has something to work with.
        """

        size_bytes = path.stat().st_size
        try:
            image_bytes = path.read_bytes()
        except OSError as exc:
            return AttachmentAnalysis(
                file_id=platform_file.id,
                filename=platform_file.filename,
                kind="image",
                ok=False,
                summary="Não foi possível ler o conteúdo da imagem.",
                error=str(exc),
            )

        vision_summary = self._call_vision(image_bytes, platform_file)
        summary = vision_summary or (
            "Imagem recebida como referência. Nenhum modelo vision habilitado "
            "no momento — confirme o objetivo em texto (forma, features e "
            "proporções) para eu reproduzir a peça."
        )

        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind="image",
            ok=True,
            summary=summary,
            metrics={"size_bytes": size_bytes},
            suggestions=[
                (
                    "Confirme com o usuário as dimensões aproximadas em mm, "
                    "a imagem só dá proporções."
                ),
                (
                    "Pergunte se a peça é decorativa/funcional e o processo "
                    "(impressão FDM/SLA, usinagem)."
                ),
            ],
        )

    def _resolve_vision_model(self) -> ModelConfig | None:
        """Escolhe um modelo multimodal habilitado para a análise vision.

        Preferência: modelos com capability ``vision``; senão, modelos ``chat``
        de provedores que sabemos montar blocos de imagem (Anthropic/OpenAI).
        ``None`` => sem modelo vision => o caller cai no resumo metadata-only.
        """
        if self._vision_model is not None:
            return self._vision_model
        if not hasattr(self.store, "list_models"):
            return None
        try:
            models = [m for m in self.store.list_models() if getattr(m, "enabled", True)]
        except Exception:  # noqa: BLE001 - resolução é best-effort
            return None
        vision = [m for m in models if ModelCapability.vision in m.capabilities]
        pool = vision or [m for m in models if ModelCapability.chat in m.capabilities]
        if not pool:
            return None
        return next((m for m in pool if getattr(m, "default", False)), None) or pool[0]

    def _call_vision(self, image_bytes: bytes, platform_file: PlatformFile) -> str | None:
        """Análise vision real (F4): manda a imagem ao LLM multimodal.

        Monta uma mensagem com texto + bloco de imagem no formato do provedor
        do modelo escolhido (``llm_gateway.multimodal``) e coleta a descrição
        estruturada da peça via ``stream_chat``. Best-effort: qualquer falha
        (sem modelo, rede, timeout) devolve ``None`` e o caller usa o resumo
        metadata-only — o chat nunca quebra por causa da análise.
        """
        model = self._resolve_vision_model()
        if model is None:
            logger.debug(
                "Sem modelo vision habilitado; análise metadata-only para %s.",
                platform_file.filename,
            )
            return None
        media_type = media_type_for(platform_file.filename)
        message = user_message_with_images(
            model.provider, _VISION_PROMPT, [(image_bytes, media_type)]
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _VISION_SYSTEM},
            message,
        ]
        try:
            text = _run_coro(self._collect_vision(model, messages))
        except Exception as exc:  # noqa: BLE001 - defensive: never crash chat
            logger.warning("Falha na análise vision de %s: %s", platform_file.filename, exc)
            return None
        text = (text or "").strip()
        return text or None

    async def _collect_vision(self, model: ModelConfig, messages: list[dict[str, Any]]) -> str:
        """Acumula os tokens do ``stream_chat`` num texto, com timeout."""

        async def _run() -> str:
            chunks: list[str] = []
            async for event in self.gateway.stream_chat(model, messages):
                if event.kind == "token":
                    chunks.append(event.content)
            return "".join(chunks)

        # Honra o timeout configurado (docstring: default 15 s); não força um
        # piso de 60 s que ignorava o valor configurado.
        return await asyncio.wait_for(_run(), timeout=self.timeout_seconds)

    # ------------------------------------------------------------------
    # internals — mesh / blend
    # ------------------------------------------------------------------

    def _analyze_mesh(
        self, platform_file: PlatformFile, path: Path, *, kind: AttachmentKind
    ) -> AttachmentAnalysis:
        """Run ``blender.validate_printability`` headless against the file."""

        if not self.blender.is_available():
            return self._mesh_metadata_only(platform_file, path, kind=kind)

        step = ModelingPlanStep(
            seq=1,
            title="Analisar anexo 3D",
            software=ModelingSoftware.blender,
            tool_name="blender.validate_printability",
            risk_level=ModelingRiskLevel.low,
            approval_required=False,
            input_json={
                "checks": [
                    "non_manifold",
                    "loose_parts",
                    "volume",
                    "bounding_box",
                ],
                "source_path": str(path),
                "file_id": platform_file.id,
            },
        )
        try:
            output = self.blender.execute(
                step,
                plan_id=f"attachment-{platform_file.id}",
                project_id=None,
            )
        except Exception as exc:  # noqa: BLE001 - never break the chat
            logger.warning(
                "Blender headless analysis failed for %s: %s",
                platform_file.filename,
                exc,
            )
            return self._mesh_metadata_only(platform_file, path, kind=kind, note=str(exc))

        ok = bool(output.get("ok"))
        result = output.get("result") if isinstance(output.get("result"), dict) else {}
        metrics = self._mesh_metrics_from_blender(result, path)
        suggestions = self._mesh_suggestions(result)
        summary = self._mesh_summary(platform_file, kind, ok, metrics, result)

        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind=kind,
            ok=ok,
            summary=summary,
            metrics=metrics,
            suggestions=suggestions,
            error=None if ok else str(output.get("message") or "blender_analysis_failed"),
        )

    def _mesh_metadata_only(
        self,
        platform_file: PlatformFile,
        path: Path,
        *,
        kind: AttachmentKind,
        note: str | None = None,
    ) -> AttachmentAnalysis:
        size_bytes = path.stat().st_size
        ext = path.suffix.lower().lstrip(".") or "?"
        summary = (
            f"Arquivo 3D {platform_file.filename} ({ext.upper()}, "
            f"{size_bytes // 1024} KB). Análise profunda indisponível porque "
            "o adapter Blender não está configurado neste backend; "
            "registre dimensões/objetivo no chat."
        )
        if note:
            summary = f"{summary} ({note})"
        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind=kind,
            ok=True,
            summary=summary,
            metrics={"size_bytes": size_bytes, "extension": ext},
            suggestions=[
                "Confirme com o usuário se este arquivo é referência de forma ou base para editar.",
                "Sem Blender configurado, peça dimensões críticas em mm explicitamente.",
            ],
        )

    @staticmethod
    def _mesh_metrics_from_blender(result: dict[str, Any], path: Path) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "size_bytes": path.stat().st_size,
            "extension": path.suffix.lower().lstrip(".") or "?",
        }
        bounding_box = result.get("bounding_box")
        if isinstance(bounding_box, dict):
            metrics["bbox_mm"] = bounding_box
        risk_score = result.get("risk_score")
        if isinstance(risk_score, (int, float)):
            metrics["risk_score"] = float(risk_score)
        per_object = result.get("metrics") or {}
        if isinstance(per_object, dict):
            for key in ("volume_mm3", "vertex_count", "edge_count", "face_count"):
                value = per_object.get(key)
                if isinstance(value, (int, float)):
                    metrics[key] = value
        return metrics

    @staticmethod
    def _mesh_suggestions(result: dict[str, Any]) -> list[str]:
        raw = result.get("recommendations") if isinstance(result, dict) else []
        if isinstance(raw, list):
            cleaned = [str(item).strip() for item in raw if str(item).strip()]
        else:
            cleaned = []
        if not cleaned:
            cleaned = [
                "Pergunte ao usuário se este arquivo será editado ou só serve de referência.",
                "Confirme se as dimensões atuais já estão na escala desejada.",
            ]
        return cleaned

    @staticmethod
    def _mesh_summary(
        platform_file: PlatformFile,
        kind: AttachmentKind,
        ok: bool,
        metrics: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        if ok:
            base = result.get("message") if isinstance(result, dict) else None
            if isinstance(base, str) and base.strip():
                return base.strip()
            ext = metrics.get("extension", "?")
            return f"Análise headless concluída para {platform_file.filename} ({ext.upper()})."
        if isinstance(result, dict) and isinstance(result.get("message"), str):
            return f"Análise headless falhou: {result['message']}"
        return "Análise headless falhou; sem detalhes do adapter."

    # ------------------------------------------------------------------
    # internals — CAD (.step)
    # ------------------------------------------------------------------

    def _analyze_cad_metadata(self, platform_file: PlatformFile, path: Path) -> AttachmentAnalysis:
        size_bytes = path.stat().st_size
        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind="cad",
            ok=True,
            summary=(
                f"Arquivo CAD STEP recebido ({size_bytes // 1024} KB). "
                "Análise profunda requer Fusion conectado — quando disponível, "
                "podemos extrair corpos, features e printability."
            ),
            metrics={"size_bytes": size_bytes, "extension": "step"},
            suggestions=[
                "Confirme se vai editar o STEP existente ou usar como referência.",
                "Pergunte parâmetros chave do design para usar set_parameter em edições.",
            ],
        )

    # ------------------------------------------------------------------
    # internals — file resolution
    # ------------------------------------------------------------------

    def _load_file(self, file_id: str) -> PlatformFile | None:
        if hasattr(self.store, "get_platform_file"):
            return self.store.get_platform_file(file_id)
        if hasattr(self.store, "list_platform_files"):
            for item in self.store.list_platform_files():
                if item.id == file_id:
                    return item
        return None

    def _is_within_size_limit(self, platform_file: PlatformFile) -> bool:
        size = platform_file.size_bytes or 0
        return size <= self.max_bytes


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_attachment(platform_file: PlatformFile) -> AttachmentKind:
    """Decide which analyser path a :class:`PlatformFile` should follow."""

    extension = Path(platform_file.filename).suffix.lower()
    content_type = (platform_file.content_type or "").lower()
    if extension in IMAGE_EXTENSIONS or content_type.startswith("image/"):
        return "image"
    if extension in MESH_EXTENSIONS or content_type in {
        "model/stl",
        "model/obj",
        "model/3mf",
    }:
        return "mesh"
    if extension in BLEND_EXTENSIONS or content_type == "application/x-blender":
        return "blend"
    if extension in CAD_EXTENSIONS or content_type == "model/step":
        return "cad"
    return "unsupported"


__all__ = [
    "AttachmentAnalysis",
    "AttachmentKind",
    "BLEND_EXTENSIONS",
    "CAD_EXTENSIONS",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "IMAGE_EXTENSIONS",
    "MESH_EXTENSIONS",
    "ModelingAttachmentAnalyzer",
    "classify_attachment",
]
