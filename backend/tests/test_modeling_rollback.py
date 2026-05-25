"""T3.6: rollback da última edição (timeline do Fusion).

Cobre o serviço (`ModelingService.rollback_last_edit`) com store + executor
falsos (sem Postgres/MCP, livre de poluição) e a rota
`POST /api/3d/plans/{id}/rollback` com um serviço stub (sem store/MCP).
A captura do marcador (orchestrator) é testada em ``test_chat_orchestrator``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.contracts import (
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanKind,
    ModelingPlanStatus,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.main import app
from app.modeling.service import (
    ModelingRollbackUnavailable,
    ModelingService,
)


class _FakeServiceStore:
    """Store mínima coberta por ``rollback_last_edit`` (sem Postgres)."""

    def __init__(self) -> None:
        self.plans: dict[str, ModelingPlan] = {}
        self.audit_events: list = []

    def get_modeling_plan(self, plan_id: str) -> ModelingPlan | None:
        return self.plans.get(plan_id)

    def upsert_modeling_plan(self, plan: ModelingPlan) -> ModelingPlan:
        self.plans[plan.id] = plan
        return plan

    def add_audit_event(self, event) -> object:
        self.audit_events.append(event)
        return event


def _edit_plan(*, marker: int | None) -> ModelingPlan:
    return ModelingPlan(
        prompt="furo lateral 6mm",
        software_choice=ModelingSoftware.fusion,
        kind=ModelingPlanKind.edit,
        parent_plan_id="m3d_plan_primary",
        rollback_marker=marker,
        status=ModelingPlanStatus.completed,
    )


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------


def test_rollback_last_edit_builds_and_executes_rollback_plan() -> None:
    store = _FakeServiceStore()
    edit = _edit_plan(marker=4)
    store.plans[edit.id] = edit
    service = ModelingService(store=store)

    executed: dict[str, ModelingPlan] = {}

    class _FakeExec:
        def execute_plan(self, plan: ModelingPlan) -> ModelingExecutionResult:
            executed["plan"] = plan
            return ModelingExecutionResult(
                plan=plan.model_copy(update={"status": ModelingPlanStatus.completed}),
                executed_step_ids=[s.id for s in plan.steps],
                blocked_step_ids=[],
                events=[],
                tool_call_ids=[],
            )

    service.executor = _FakeExec()  # type: ignore[assignment]

    result = service.rollback_last_edit(edit.id)

    rb = executed["plan"]
    assert len(rb.steps) == 1
    assert rb.steps[0].tool_name == "fusion.rollback_timeline"
    assert rb.steps[0].input_json == {"target_count": 4}
    assert rb.steps[0].status is ModelingStepStatus.approved
    assert rb.steps[0].approval_required is False
    assert rb.parent_plan_id == "m3d_plan_primary"
    assert rb.status is ModelingPlanStatus.approved
    assert result.plan.status is ModelingPlanStatus.completed
    assert any(e.event_type == "modeling.plan_rollback_requested" for e in store.audit_events)


def test_rollback_last_edit_raises_without_marker() -> None:
    store = _FakeServiceStore()
    edit = _edit_plan(marker=None)
    store.plans[edit.id] = edit
    service = ModelingService(store=store)

    with pytest.raises(ModelingRollbackUnavailable):
        service.rollback_last_edit(edit.id)


def test_rollback_last_edit_raises_keyerror_for_missing_plan() -> None:
    service = ModelingService(store=_FakeServiceStore())

    with pytest.raises(KeyError):
        service.rollback_last_edit("m3d_plan_missing")


# ---------------------------------------------------------------------------
# route (service stubbed — sem store/MCP)
# ---------------------------------------------------------------------------


def _stub_service(monkeypatch, stub: object) -> None:
    from app.api.routes import modeling as modeling_route

    monkeypatch.setattr(modeling_route, "_service", lambda: stub)


def test_rollback_route_returns_execution_on_success(monkeypatch) -> None:
    rb_plan = ModelingPlan(
        prompt="rollback",
        software_choice=ModelingSoftware.fusion,
        kind=ModelingPlanKind.edit,
        status=ModelingPlanStatus.completed,
    )

    class _Stub:
        def rollback_last_edit(self, plan_id: str) -> ModelingExecutionResult:
            return ModelingExecutionResult(
                plan=rb_plan,
                executed_step_ids=[],
                blocked_step_ids=[],
                events=[],
                tool_call_ids=[],
            )

    _stub_service(monkeypatch, _Stub())
    resp = TestClient(app).post("/api/3d/plans/m3d_plan_x/rollback")

    assert resp.status_code == 200
    assert resp.json()["plan"]["status"] == "completed"


def test_rollback_route_returns_409_when_unavailable(monkeypatch) -> None:
    class _Stub:
        def rollback_last_edit(self, plan_id: str) -> ModelingExecutionResult:
            raise ModelingRollbackUnavailable(plan_id)

    _stub_service(monkeypatch, _Stub())
    resp = TestClient(app).post("/api/3d/plans/m3d_plan_x/rollback")

    assert resp.status_code == 409


def test_rollback_route_returns_404_when_missing(monkeypatch) -> None:
    class _Stub:
        def rollback_last_edit(self, plan_id: str) -> ModelingExecutionResult:
            raise KeyError(plan_id)

    _stub_service(monkeypatch, _Stub())
    resp = TestClient(app).post("/api/3d/plans/missing/rollback")

    assert resp.status_code == 404
