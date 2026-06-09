"""F7 (P5) — wiring do resolver no executor (probe→resolve→dispatch, flag-gated).

Exercita ``ModelingExecutorService._maybe_resolve_spatial`` (decisão + probe +
inline/expansão) e ``_run_expanded_steps`` (agregação) sem Fusion: a captura de
geometria é canada via monkeypatch de ``capture_model_state``. Flag OFF = no-op.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelState,
    ModelStateBody,
    ModelStateFace,
)
from app.modeling.executor import ModelingExecutorService, _StepOutcome
from app.modeling.spatial_ref import RELATIVE_COORD_FORBIDDEN, SpatialRefError


def _state() -> ModelState:
    return ModelState(
        bodies=[
            ModelStateBody(
                name="Caixa",
                bbox_min_mm=[0, 0, 0],
                bbox_max_mm=[60, 40, 20],
                faces=[
                    ModelStateFace(
                        token="CAIXA_TOP", type="planar", normal_axis="+z", center_mm=[30, 20, 20]
                    ),
                ],
                edges=[],
            ),
            ModelStateBody(
                name="Tampa",
                bbox_min_mm=[0, 0, 20],
                bbox_max_mm=[60, 40, 23],
                faces=[
                    ModelStateFace(
                        token="TAMPA_BOTTOM",
                        type="planar",
                        normal_axis="-z",
                        center_mm=[30, 20, 20],
                    ),
                ],
            ),
        ]
    )


def _executor() -> ModelingExecutorService:
    # _maybe_resolve_spatial só usa self._tracer (no-op p/ store sem
    # record_trace_events_bulk) e capture_model_state (monkeypatched nos testes).
    return ModelingExecutorService(
        store=object(), mcp_client=object(), snapshots=object(), artifacts=object()
    )


def _plan() -> ModelingPlan:
    return ModelingPlan(
        prompt="x", software_choice=ModelingSoftware.fusion, status=ModelingPlanStatus.approved
    )


def _step(tool: str, **args: object) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title="t",
        software=ModelingSoftware.fusion,
        tool_name=tool,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json=dict(args),
    )


def _enable(monkeypatch: pytest.MonkeyPatch, state: ModelState | None = _state()) -> None:
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", True, raising=False)
    monkeypatch.setattr("app.modeling.model_state.capture_model_state", lambda _exec, _plan: state)


def test_flag_off_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", False, raising=False)
    ex = _executor()
    step = _step("fusion.add_cylinder", origin_mm="@token('CAIXA_TOP').center")
    out_step, expanded = ex._maybe_resolve_spatial(step, plan=_plan())
    assert expanded is None and out_step is step  # intacto, sem probe


def test_inline_ref_rewritten_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    ex = _executor()
    step = _step("fusion.add_cylinder", origin_mm="@token('CAIXA_TOP').center", diameter_mm=5)
    out_step, expanded = ex._maybe_resolve_spatial(step, plan=_plan())
    assert expanded is None  # inline: 1→1
    assert out_step.input_json["origin_mm"] == [30, 20, 20]
    assert out_step.input_json["diameter_mm"] == 5


def test_place_body_expands_to_concrete_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    ex = _executor()
    step = _step(
        "fusion.place_body",
        body="Tampa",
        anchor="@token('TAMPA_BOTTOM')",
        target="@token('CAIXA_TOP')",
        mate="flush",
    )
    out_step, expanded = ex._maybe_resolve_spatial(step, plan=_plan())
    assert out_step is step
    assert expanded is not None
    # place_body → move_body determinístico (mede as faces, calcula o delta).
    assert [s.tool_name for s in expanded] == ["fusion.move_body"]
    assert all(s.status is ModelingStepStatus.approved for s in expanded)


def test_unresolved_token_raises_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    ex = _executor()
    step = _step("fusion.add_cylinder", origin_mm="@token('GHOST').center")
    with pytest.raises(SpatialRefError):
        ex._maybe_resolve_spatial(step, plan=_plan())


def test_absolute_coordinates_skip_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    # Flag ON mas passo sem ref: não precisa de probe nem reescrita (regressão).
    _enable(monkeypatch, state=None)  # se chamasse o probe, state=None quebraria refs
    ex = _executor()
    step = _step("fusion.add_box", center_mm=[10, 20, 30], width_mm=40)
    out_step, expanded = ex._maybe_resolve_spatial(step, plan=_plan())
    assert expanded is None and out_step is step


def test_relative_enforcement_rejects_chute_move(monkeypatch: pytest.MonkeyPatch) -> None:
    # F9 Pilar 3: flag ON + move_body cuja coordenada absoluta enfia a Tampa
    # (z=20..23) DENTRO da caixa (z=0..20) → SpatialRefError tipado no executor.
    monkeypatch.setattr(settings, "modeling_relative_enforcement_enabled", True, raising=False)
    monkeypatch.setattr("app.modeling.model_state.capture_model_state", lambda _e, _p: _state())
    ex = _executor()
    step = _step("fusion.move_body", body_ref="Tampa", translation_mm=[0, 0, -10])
    with pytest.raises(SpatialRefError) as exc:
        ex._maybe_resolve_spatial(step, plan=_plan())
    assert exc.value.code == RELATIVE_COORD_FORBIDDEN


def test_relative_enforcement_off_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Flag OFF (default): o move_body "chute" passa direto, sem probe (regressão).
    monkeypatch.setattr(settings, "modeling_relative_enforcement_enabled", False, raising=False)
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", False, raising=False)
    ex = _executor()
    step = _step("fusion.move_body", body_ref="Tampa", translation_mm=[0, 0, -10])
    out_step, expanded = ex._maybe_resolve_spatial(step, plan=_plan())
    assert expanded is None and out_step is step


def test_relative_enforcement_exempts_expanded_concretes(monkeypatch: pytest.MonkeyPatch) -> None:
    # O move_body que o RESOLVER emite (from_expansion=True) é o delta JÁ medido —
    # NÃO passa pelo Gate B (senão um place_body align=coplanar/edge com offset
    # lateral de propósito seria falso-recusado). Mesmo move que sobreporia passa.
    monkeypatch.setattr(settings, "modeling_relative_enforcement_enabled", True, raising=False)
    monkeypatch.setattr("app.modeling.model_state.capture_model_state", lambda _e, _p: _state())
    ex = _executor()
    step = _step("fusion.move_body", body_ref="Tampa", translation_mm=[0, 0, -10])
    out_step, expanded = ex._maybe_resolve_spatial(step, plan=_plan(), from_expansion=True)
    assert expanded is None and out_step is step  # isento — sem SpatialRefError


def test_run_expanded_aggregates_success(monkeypatch: pytest.MonkeyPatch) -> None:
    ex = _executor()
    calls: list[str] = []

    def fake(step: ModelingPlanStep, *, plan: ModelingPlan, **_kw: object) -> _StepOutcome:
        calls.append(step.tool_name)
        return _StepOutcome(
            step=step.model_copy(update={"status": ModelingStepStatus.completed}),
            output={"ok": True, "message": "ok"},
            tool_call_id="tc",
            event="e",
            ok=True,
        )

    monkeypatch.setattr(ex, "_execute_single_step", fake)
    concrete = [_step("fusion.make_component"), _step("fusion.joint")]
    outcome = ex._run_expanded_steps(_step("fusion.place_body"), concrete, _plan())
    assert outcome.ok is True
    assert calls == ["fusion.make_component", "fusion.joint"]
    assert outcome.output["expanded"] == [
        {"tool_name": "fusion.make_component", "ok": True},
        {"tool_name": "fusion.joint", "ok": True},
    ]
    assert outcome.step.status is ModelingStepStatus.completed


def test_run_expanded_preserves_subprovenance_for_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bug do laudo (A): _run_expanded_steps descartava o _provenance dos concretos
    # → history_from_plan via vazio p/ TODO placement/relação (auto-crítica cega).
    # Garante que o _provenance de cada sub-passo sobrevive no agregado E é
    # recuperável por history_from_plan (round-trip executor→histórico).
    from app.modeling.provenance import build_change_record, history_from_plan

    ex = _executor()
    before = ModelState(bodies=[])
    after = ModelState(bodies=[ModelStateBody(name="Tampa", stable_id="ID1")])
    prov = build_change_record(
        "fusion.make_component", before, after, category="mutative", seq=1
    ).model_dump(mode="json")

    def fake(step: ModelingPlanStep, *, plan: ModelingPlan, **_kw: object) -> _StepOutcome:
        out: dict = {"ok": True}
        if step.tool_name == "fusion.make_component":
            out["_provenance"] = prov
        return _StepOutcome(
            step=step.model_copy(update={"status": ModelingStepStatus.completed}),
            output=out,
            tool_call_id=None,
            event="e",
            ok=True,
        )

    monkeypatch.setattr(ex, "_execute_single_step", fake)
    concrete = [_step("fusion.make_component"), _step("fusion.joint")]
    outcome = ex._run_expanded_steps(_step("fusion.place_body"), concrete, _plan())
    # o _provenance do concreto sobrevive no agregado…
    assert outcome.output["expanded"][0]["_provenance"]["tool_name"] == "fusion.make_component"
    # …e history_from_plan o recupera do plano persistido (antes do fix, vazio).
    plan = _plan()
    plan.steps = [outcome.step]
    hist = history_from_plan(plan)
    assert hist is not None and len(hist.records) == 1
    assert hist.records[0].tool_name == "fusion.make_component"


def test_run_expanded_blocks_high_risk_concrete(monkeypatch: pytest.MonkeyPatch) -> None:
    # Constituição: a expansão NÃO pode auto-executar um concreto high_risk
    # (combine_bodies). Pré-varre e bloqueia ANTES de executar qualquer passo.
    ex = _executor()
    called: list[str] = []
    monkeypatch.setattr(
        ex,
        "_execute_single_step",
        lambda s, *, plan, **_kw: (
            called.append(s.tool_name)
            or _StepOutcome(step=s, output={"ok": True}, tool_call_id=None, event="e", ok=True)
        ),
    )
    concrete = [_step("fusion.add_cylinder"), _step("fusion.combine_bodies")]
    outcome = ex._run_expanded_steps(_step("fusion.distribute_along"), concrete, _plan())
    assert outcome.ok is False
    assert called == []  # nada executou (fail-safe, sem corpos soltos)
    assert outcome.output["error_code"] == "fusion.spatial_expansion_requires_approval"


def test_run_expanded_does_not_reblock_inherited_high_risk_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Gate é pela CATEGORIA intrínseca: make_component/joint (mutative) NÃO
    # bloqueiam mesmo herdando risk_level=high de um declarativo já aprovado.
    ex = _executor()
    called: list[str] = []
    monkeypatch.setattr(
        ex,
        "_execute_single_step",
        lambda s, *, plan, **_kw: (
            called.append(s.tool_name)
            or _StepOutcome(step=s, output={"ok": True}, tool_call_id=None, event="e", ok=True)
        ),
    )
    high = ModelingRiskLevel.high
    concrete = [
        _step("fusion.make_component"),
        ModelingPlanStep(
            seq=1,
            title="j",
            software=ModelingSoftware.fusion,
            tool_name="fusion.joint",
            risk_level=high,
            approval_required=False,
            status=ModelingStepStatus.approved,
            input_json={},
        ),
    ]
    outcome = ex._run_expanded_steps(_step("fusion.place_body"), concrete, _plan())
    assert outcome.ok is True
    assert called == ["fusion.make_component", "fusion.joint"]  # executou, não bloqueou


def test_run_expanded_stops_on_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ex = _executor()
    calls: list[str] = []

    def fake(step: ModelingPlanStep, *, plan: ModelingPlan, **_kw: object) -> _StepOutcome:
        calls.append(step.tool_name)
        ok = step.tool_name == "fusion.joint"  # make_component FALHA primeiro
        return _StepOutcome(
            step=step, output={"ok": ok, "message": "x"}, tool_call_id=None, event="e", ok=ok
        )

    monkeypatch.setattr(ex, "_execute_single_step", fake)
    concrete = [_step("fusion.make_component"), _step("fusion.joint")]
    outcome = ex._run_expanded_steps(_step("fusion.place_body"), concrete, _plan())
    assert outcome.ok is False
    assert calls == ["fusion.make_component"]  # joint NÃO executou (depende do 1º)
    assert outcome.step.status is ModelingStepStatus.failed
