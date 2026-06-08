"""Testes F8 (Sub 4) — resolução de relação + wiring no executor.

``resolve_relation`` deriva (medindo) e expande nas primitivas F7 concretas
(make_component + joint). O executor só resolve relate_bodies com a flag ON;
flag OFF = no-op (zero regressão). Erro de relação é tipado (SpatialRefError).
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingSoftware,
    ModelingStepStatus,
    ModelState,
    ModelStateBody,
    ModelStateFace,
)
from app.modeling.executor import ModelingExecutorService
from app.modeling.relation_derive import RelationUnderivableError
from app.modeling.relation_resolver import resolve_relation, spec_from_args


def _face(token, normal, *, area=1000.0, center=None):
    return ModelStateFace(
        token=token, type="planar", normal_axis=normal, area_mm2=area, center_mm=center
    )


def _state() -> ModelState:
    tampa = ModelStateBody(
        name="Tampa",
        stable_id="Tampa_id",
        bbox_min_mm=[0, 0, 20],
        bbox_max_mm=[60, 40, 23],
        faces=[_face("tampa_bottom", "-z", center=[30, 20, 20])],
    )
    caixa = ModelStateBody(
        name="Caixa",
        stable_id="Caixa_id",
        bbox_min_mm=[0, 0, 0],
        bbox_max_mm=[60, 40, 20],
        faces=[_face("caixa_top", "+z", center=[30, 20, 20])],
    )
    return ModelState(bodies=[tampa, caixa])


def test_spec_from_args_cleans_at_refs() -> None:
    spec = spec_from_args(
        {"kind": "flush_mate", "moving": "@body('Tampa')", "reference": "@('Caixa')"}
    )
    assert spec.moving == "Tampa" and spec.reference == "Caixa" and spec.kind == "flush_mate"


def test_spec_from_args_requires_fields() -> None:
    with pytest.raises(RelationUnderivableError):
        spec_from_args({"kind": "flush_mate", "moving": "Tampa"})


def test_resolve_relation_expands_to_component_and_joint() -> None:
    concrete, actions = resolve_relation(
        {"kind": "flush_mate", "moving": "Tampa", "reference": "Caixa"}, _state()
    )
    tools = [c.tool_name for c in concrete]
    assert tools == ["fusion.make_component", "fusion.joint"]
    joint = concrete[1].input_json
    assert joint["joint_type"] == "rigid"
    assert joint["face_token_one"] == "tampa_bottom"
    assert joint["face_token_two"] == "caixa_top"
    assert joint["body_two"] == "Caixa"
    # a primeira ação registra a derivação da relação (telemetria/auditoria).
    assert actions[0].kind == "derive_relation"


def test_resolve_relation_unknown_kind_is_typed() -> None:
    with pytest.raises(RelationUnderivableError):
        resolve_relation({"kind": "teleport", "moving": "Tampa", "reference": "Caixa"}, _state())


# --------------------------------------------------------------------------- #
# Wiring no executor — flag-gated                                             #
# --------------------------------------------------------------------------- #
def _executor() -> ModelingExecutorService:
    return ModelingExecutorService(
        store=object(), mcp_client=object(), snapshots=object(), artifacts=object()
    )


def _plan() -> ModelingPlan:
    return ModelingPlan(
        prompt="x", software_choice=ModelingSoftware.fusion, status=ModelingPlanStatus.approved
    )


def _relate_step() -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title="relate",
        software=ModelingSoftware.fusion,
        tool_name="fusion.relate_bodies",
        status=ModelingStepStatus.approved,
        input_json={"kind": "flush_mate", "moving": "Tampa", "reference": "Caixa"},
    )


def test_executor_resolves_relation_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "modeling_relation_placement_enabled", True, raising=False)
    monkeypatch.setattr("app.modeling.model_state.capture_model_state", lambda _e, _p: _state())
    step, expanded = _executor()._maybe_resolve_spatial(_relate_step(), plan=_plan())
    assert expanded is not None
    assert [s.tool_name for s in expanded] == ["fusion.make_component", "fusion.joint"]


def test_executor_noop_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "modeling_relation_placement_enabled", False, raising=False)
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", False, raising=False)
    step, expanded = _executor()._maybe_resolve_spatial(_relate_step(), plan=_plan())
    # flag OFF: não resolve (o passo crua erraria claro no adapter).
    assert expanded is None


def test_executor_skips_relate_when_only_spatial_on(monkeypatch: pytest.MonkeyPatch) -> None:
    # Laudo (H): relation OFF + spatial ON + @body refs — relate_bodies NÃO pode
    # ser capturado pelo caminho F7 (o leftover-ref guard daria erro enganoso
    # "campo não suportado: moving"). Deve cair limpo no adapter (expanded=None).
    monkeypatch.setattr(settings, "modeling_relation_placement_enabled", False, raising=False)
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", True, raising=False)
    step = ModelingPlanStep(
        seq=1,
        title="relate",
        software=ModelingSoftware.fusion,
        tool_name="fusion.relate_bodies",
        status=ModelingStepStatus.approved,
        input_json={
            "kind": "flush_mate",
            "moving": "@body('Tampa')",
            "reference": "@body('Caixa')",
        },
    )
    _step_out, expanded = _executor()._maybe_resolve_spatial(step, plan=_plan())
    assert expanded is None  # fallthrough limpo ao adapter, sem erro enganoso F7
