"""Loop de verificação VISUAL (motor genérico, passo 3) — sem Fusion.

Cobre: o probe de render (`capture_viewport_image`), a crítica multimodal
(`critique_render` monta mensagem com a imagem + devolve o veredito) e o loop
`run_visual_correction` (render→crítica→replan edição→re-render→re-crítica),
incluindo a flag OFF (no-op) e o caso "corresponde" (sem correção).

A captura real e a fidelidade da visão são gate do dono no Fusion real.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from app.core.contracts import (
    ModelCapability,
    ModelConfig,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingSoftware,
    ProviderName,
)
from app.modeling import visual_critique as vc

PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode("ascii")


def _vision_model() -> ModelConfig:
    return ModelConfig(
        id="openai/vision",
        provider=ProviderName.openai,
        display_name="GPT Vision",
        provider_model_id="gpt-5-mini",
        capabilities=[ModelCapability.chat, ModelCapability.vision],
        default=True,
    )


def _fusion_plan() -> ModelingPlan:
    return ModelingPlan(
        prompt="caixa com tampa que abre por dobradiça",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.approved,
    )


class _Outcome:
    def __init__(self, ok: bool, output: Any) -> None:
        self.ok = ok
        self.output = output


def _capture_output(b64: str | None) -> dict[str, Any]:
    inner: dict[str, Any] = {"ok": True, "image_format": "png"}
    if b64 is not None:
        inner["image_base64"] = b64
    blob = json.dumps(inner)
    return {"ok": True, "result": {"message": blob}, "message": blob, "software": "fusion"}


class _FakeExecutor:
    def __init__(self, capture_b64: str | None = PNG_B64) -> None:
        self._capture = capture_b64
        self.executed: list[Any] = []
        self.probe_calls = 0
        self.store = None

    def _execute_single_step(self, step: Any, *, plan: Any) -> _Outcome:
        self.probe_calls += 1
        return _Outcome(True, _capture_output(self._capture))

    def execute_plan(self, plan: Any) -> Any:
        self.executed.append(plan)
        return plan


class _FakeVisionGateway:
    """Devolve vereditos de uma fila; registra a última mensagem (multimodal)."""

    def __init__(self, verdicts: list[dict[str, Any]]) -> None:
        self._verdicts = list(verdicts)
        self.calls = 0
        self.last_messages: Any = None

    async def generate_structured(
        self, *, model: Any, messages: Any, schema_name: str, schema: Any
    ) -> dict[str, Any]:
        self.calls += 1
        self.last_messages = messages
        if self._verdicts:
            return self._verdicts.pop(0)
        return {"matches_intent": True, "issues": [], "suggestion": "", "confidence": 1.0}


class _FakePlanner:
    def __init__(self, gateway: Any, model: ModelConfig | None) -> None:
        self.gateway = gateway
        self._model = model
        self.created: list[Any] = []

    def _resolve_planner_model(self) -> ModelConfig | None:
        return self._model

    def create_plan(self, payload: Any, *, live_state_block: str | None = None) -> Any:
        self.created.append(payload)
        return ModelingPlan(
            prompt=payload.prompt,
            software_choice=ModelingSoftware.fusion,
            status=ModelingPlanStatus.approved,
        )


# ---------------------------------------------------------------------------
# capture_viewport_image
# ---------------------------------------------------------------------------


def test_capture_viewport_image_unwraps_envelope() -> None:
    out = vc.capture_viewport_image(_FakeExecutor(PNG_B64), _fusion_plan())
    assert out == PNG_B64


def test_capture_viewport_image_none_without_image() -> None:
    assert vc.capture_viewport_image(_FakeExecutor(None), _fusion_plan()) is None


def test_capture_viewport_image_skips_non_fusion() -> None:
    plan = ModelingPlan(
        prompt="x",
        software_choice=ModelingSoftware.blender,
        status=ModelingPlanStatus.approved,
    )
    ex = _FakeExecutor()
    assert vc.capture_viewport_image(ex, plan) is None
    assert ex.probe_calls == 0


# ---------------------------------------------------------------------------
# critique_render
# ---------------------------------------------------------------------------


def test_critique_render_sends_image_and_returns_verdict() -> None:
    gw = _FakeVisionGateway(
        [
            {
                "matches_intent": False,
                "issues": ["knuckles no lado errado"],
                "suggestion": "mover",
                "confidence": 0.7,
            }
        ]
    )
    verdict = vc.critique_render(gw, _vision_model(), rendered_b64=PNG_B64, intent="caixa")

    assert verdict is not None and verdict["matches_intent"] is False
    assert "knuckles no lado errado" in verdict["issues"]
    # a mensagem foi multimodal (texto + imagem)
    user_msg = gw.last_messages[-1]
    assert isinstance(user_msg["content"], list)
    assert any(b.get("type") == "input_image" for b in user_msg["content"])


# ---------------------------------------------------------------------------
# run_visual_correction
# ---------------------------------------------------------------------------


def test_run_visual_correction_noop_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", False, raising=False)
    ex = _FakeExecutor()
    planner = _FakePlanner(_FakeVisionGateway([]), _vision_model())
    assert vc.run_visual_correction(ex, planner, _fusion_plan()) is None
    assert ex.probe_calls == 0  # nem renderiza


def test_run_visual_correction_no_fix_when_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", True, raising=False)
    gw = _FakeVisionGateway(
        [{"matches_intent": True, "issues": [], "suggestion": "", "confidence": 0.9}]
    )
    planner = _FakePlanner(gw, _vision_model())
    ex = _FakeExecutor()

    verdict = vc.run_visual_correction(ex, planner, _fusion_plan())

    assert verdict is not None and verdict["matches_intent"] is True
    assert planner.created == []  # não replanejou
    assert ex.executed == []


def test_run_visual_correction_replans_then_converges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", True, raising=False)
    monkeypatch.setattr(vc.settings, "modeling_visual_max_rounds", 2, raising=False)
    # 1ª crítica: divergente → corrige; 2ª crítica: ok.
    gw = _FakeVisionGateway(
        [
            {
                "matches_intent": False,
                "issues": ["tampa não conectada"],
                "suggestion": "combine",
                "confidence": 0.6,
            },
            {"matches_intent": True, "issues": [], "suggestion": "", "confidence": 0.95},
        ]
    )
    planner = _FakePlanner(gw, _vision_model())
    ex = _FakeExecutor()

    verdict = vc.run_visual_correction(ex, planner, _fusion_plan())

    assert verdict is not None and verdict["matches_intent"] is True
    assert len(planner.created) == 1  # replanejou 1 edição corretiva
    assert planner.created[0].kind.value == "edit"
    assert len(ex.executed) == 1  # executou a correção
    assert gw.calls == 2  # criticou 2x (antes e depois)


def test_run_visual_correction_none_without_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", True, raising=False)
    planner = _FakePlanner(_FakeVisionGateway([]), None)  # sem modelo
    assert vc.run_visual_correction(_FakeExecutor(), planner, _fusion_plan()) is None


# ---------------------------------------------------------------------------
# F8: assess_visual_findings — percepção read-only → Finding(source=semantic)
# ---------------------------------------------------------------------------


def test_assess_visual_findings_returns_semantic_on_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", True, raising=False)
    gw = _FakeVisionGateway(
        [{"matches_intent": False, "issues": ["a tampa flutua", "peça de cabeça para baixo"],
          "suggestion": "", "confidence": 0.8}]
    )
    planner = _FakePlanner(gw, _vision_model())
    findings = vc.assess_visual_findings(_FakeExecutor(), planner, _fusion_plan())
    assert len(findings) == 2
    assert all(f.source == "semantic" and f.kind == "wrong" for f in findings)
    assert all(f.check_id == "visual" and f.detail.startswith("👁 visão:") for f in findings)
    # percepção pura: NÃO replaneja (não chama create_plan/execute_plan).
    assert planner.created == []


def test_assess_visual_findings_empty_when_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", True, raising=False)
    ok = {"matches_intent": True, "issues": [], "suggestion": "", "confidence": 1.0}
    planner = _FakePlanner(_FakeVisionGateway([ok]), _vision_model())
    assert vc.assess_visual_findings(_FakeExecutor(), planner, _fusion_plan()) == []


def test_assess_visual_findings_empty_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc.settings, "modeling_visual_verification_enabled", False, raising=False)
    bad = {"matches_intent": False, "issues": ["x"], "suggestion": "", "confidence": 0.5}
    gw = _FakeVisionGateway([bad])
    planner = _FakePlanner(gw, _vision_model())
    assert vc.assess_visual_findings(_FakeExecutor(), planner, _fusion_plan()) == []
    assert gw.calls == 0  # nem renderiza/chama a visão
