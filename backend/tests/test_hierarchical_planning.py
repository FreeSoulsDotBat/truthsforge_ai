"""Testes F2 — planejamento agêntico/hierárquico.

Cobre a orquestração bloco-a-bloco (decompõe→executa→observa ModelState→
próximo bloco vê o estado real), o aborto consistente em falha de bloco, e o
despacho por flag (OFF = caminho one-shot intacto). Sem Fusion/LLM reais.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.contracts import (
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanKind,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelingSubGoal,
    ModelState,
    ModelStateBody,
)
from app.modeling.chat_orchestrator import ModelingChatOrchestrator
from app.modeling.executor import _StepOutcome


class _FakeStore:
    def __init__(self) -> None:
        self.plans: dict[str, ModelingPlan] = {}

    def upsert_modeling_plan(self, plan: ModelingPlan) -> ModelingPlan:
        self.plans[plan.id] = plan
        return plan

    def get_modeling_plan(self, plan_id: str) -> ModelingPlan | None:
        return self.plans.get(plan_id)

    def record_trace_events_bulk(self, events: list[Any]) -> None:
        pass


def _block_plan(seq: int, status: ModelingPlanStatus) -> ModelingPlan:
    return ModelingPlan(
        id=f"m3d_plan_block{seq}",
        prompt=f"bloco {seq}",
        kind=ModelingPlanKind.edit,
        parent_plan_id="m3d_plan_primary",
        software_choice=ModelingSoftware.fusion,
        status=status,
        steps=[
            ModelingPlanStep(
                seq=1,
                title=f"step do bloco {seq}",
                software=ModelingSoftware.fusion,
                tool_name="fusion.add_box",
                risk_level=ModelingRiskLevel.low,
                status=ModelingStepStatus.completed,
                input_json={},
            )
        ],
    )


class _FakePlanner:
    """Devolve blocos pré-fabricados por seq e registra o ModelState visto."""

    def __init__(self, statuses: list[ModelingPlanStatus]) -> None:
        self._statuses = statuses
        self.seen_states: list[Any] = []
        self.planned_seqs: list[int] = []

    def plan_block_for_subgoal(
        self, sub_goal, *, base_payload, parent_plan_id, model_state, done_titles
    ) -> ModelingPlan:
        self.seen_states.append(model_state)
        self.planned_seqs.append(sub_goal.seq)
        return _block_plan(sub_goal.seq, self._statuses[sub_goal.seq - 1])

    def build_corrector(self, *, max_attempts: int = 5):  # pragma: no cover - loop OFF
        return lambda step, output, attempt: step


class _FakeExecutor:
    """execute_plan devolve o bloco como está; o probe query_geometry (do
    capture_model_state) devolve um ModelState que cresce a cada bloco — assim
    o teste verifica que o bloco N+1 vê o estado deixado pelo bloco N."""

    def __init__(self, store: _FakeStore) -> None:
        self.store = store
        self._bodies = 0

    def execute_plan(self, plan: ModelingPlan) -> ModelingExecutionResult:
        return ModelingExecutionResult(
            plan=plan,
            executed_step_ids=[s.id for s in plan.steps],
            blocked_step_ids=[],
            events=[f"executed:{plan.id}"],
            tool_call_ids=[],
        )

    def _execute_single_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> _StepOutcome:
        # Só o probe query_geometry chega aqui (capture_model_state).
        self._bodies += 1
        inner = {
            "ok": True,
            "bodies": [
                {
                    "name": f"Corpo{i}",
                    "stable_id": f"sid{i}",
                    "dimensions_mm": [10, 10, 10],
                    "is_solid": True,
                    "faces": [],
                    "edges": [],
                }
                for i in range(self._bodies)
            ],
        }
        output = {
            "ok": True,
            "message": json.dumps(inner),
            "result": {"message": json.dumps(inner)},
        }
        return _StepOutcome(step=step, output=output, tool_call_id=None, event="probe", ok=True)


def _primary_with_subgoals(n: int) -> ModelingPlan:
    return ModelingPlan(
        id="m3d_plan_primary",
        prompt="caixa com tampa e dobradiça",
        kind=ModelingPlanKind.primary,
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.approved,
        sub_goals=[
            ModelingSubGoal(seq=i, title=f"Sub {i}", description=f"d{i}", acceptance=f"a{i}")
            for i in range(1, n + 1)
        ],
    )


def _orch(
    statuses: list[ModelingPlanStatus],
) -> tuple[ModelingChatOrchestrator, _FakePlanner, _FakeStore]:
    store = _FakeStore()
    planner = _FakePlanner(statuses)
    executor = _FakeExecutor(store)
    orch = ModelingChatOrchestrator(store=store, planner=planner, executor=executor)
    return orch, planner, store


def test_hierarchical_runs_blocks_in_order_and_flows_state() -> None:
    orch, planner, store = _orch([ModelingPlanStatus.completed] * 3)
    primary = _primary_with_subgoals(3)

    result = orch._run_execution_hierarchical(primary)

    # Blocos planejados na ordem dos sub-objetivos.
    assert planner.planned_seqs == [1, 2, 3]
    # Estado fluiu: bloco 1 viu estado inicial (None); blocos seguintes viram o
    # ModelState capturado (read-back) do anterior, com nº de bodies crescente.
    assert planner.seen_states[0] is None
    assert planner.seen_states[1] is not None and len(planner.seen_states[1].bodies) >= 1
    assert len(planner.seen_states[2].bodies) > len(planner.seen_states[1].bodies)
    # Resultado agregado: todos os sub-objetivos completaram.
    assert result.plan.status is ModelingPlanStatus.completed
    assert all(sg.status.value == "completed" for sg in result.plan.sub_goals)
    assert [sg.block_plan_id for sg in result.plan.sub_goals] == [
        "m3d_plan_block1",
        "m3d_plan_block2",
        "m3d_plan_block3",
    ]
    assert len(result.executed_step_ids) == 3  # 1 step por bloco


def test_hierarchical_aborts_on_block_failure() -> None:
    # Bloco 2 falha → aborta; bloco 3 nunca é planejado.
    orch, planner, store = _orch(
        [ModelingPlanStatus.completed, ModelingPlanStatus.failed, ModelingPlanStatus.completed]
    )
    primary = _primary_with_subgoals(3)

    result = orch._run_execution_hierarchical(primary)

    assert planner.planned_seqs == [1, 2]  # parou no 2
    assert result.plan.status is ModelingPlanStatus.failed
    statuses = [sg.status.value for sg in result.plan.sub_goals]
    assert statuses == ["completed", "failed", "pending"]


def test_run_execution_dispatches_hierarchical_only_with_flag_and_subgoals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modeling import chat_orchestrator as co

    orch, planner, store = _orch([ModelingPlanStatus.completed])

    # Flag OFF → mesmo com sub_goals, vai pelo caminho one-shot (não hierárquico).
    monkeypatch.setattr(co.settings, "modeling_hierarchical_planning_enabled", False)
    primary = _primary_with_subgoals(1)
    orch._run_execution(primary)
    assert planner.planned_seqs == []  # não decompôs em blocos

    # Flag ON + sub_goals → hierárquico.
    monkeypatch.setattr(co.settings, "modeling_hierarchical_planning_enabled", True)
    orch._run_execution(primary)
    assert planner.planned_seqs == [1]


def _named_block(plan_id: str, name: str) -> ModelingPlan:
    return ModelingPlan(
        id=plan_id,
        prompt="x",
        kind=ModelingPlanKind.edit,
        parent_plan_id="m3d_plan_primary",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.completed,
        steps=[
            ModelingPlanStep(
                seq=1,
                title=f"add {name}",
                software=ModelingSoftware.fusion,
                tool_name="fusion.add_box",
                status=ModelingStepStatus.completed,
                input_json={"name": name},
            )
        ],
    )


def test_hierarchical_turn_verdict_aggregates_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    # F8: o veredito agora vale COM o hierárquico ligado — agrega os corpos
    # nomeados de TODOS os blocos e pega o órfão (corpo a mais) no estado final.
    from app.core.config import settings

    monkeypatch.setattr(settings, "modeling_self_critique_enabled", True, raising=False)
    orch, _planner, store = _orch([ModelingPlanStatus.completed, ModelingPlanStatus.completed])
    store.plans["b1"] = _named_block("b1", "Caixa")
    store.plans["b2"] = _named_block("b2", "Tampa")
    primary = _primary_with_subgoals(2)
    primary.sub_goals[0].block_plan_id = "b1"
    primary.sub_goals[1].block_plan_id = "b2"
    final = ModelState(
        bodies=[
            ModelStateBody(name="Caixa", stable_id="ID1"),
            ModelStateBody(name="Tampa", stable_id="ID2"),
            ModelStateBody(name="Caixa_fixed", stable_id="ID3"),  # órfão duplicado
        ]
    )
    verdict, notice = orch._hierarchical_turn_verdict(primary, primary.sub_goals, final)
    assert verdict is not None and verdict.overall == "diverged"
    assert notice and "Caixa_fixed" in notice


def test_hierarchical_turn_verdict_off_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "modeling_self_critique_enabled", False, raising=False)
    orch, _planner, _store = _orch([ModelingPlanStatus.completed])
    primary = _primary_with_subgoals(1)
    assert orch._hierarchical_turn_verdict(primary, primary.sub_goals, None) == (None, None)
