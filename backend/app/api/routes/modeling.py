from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.contracts import (
    ModelingApprovalRequest,
    ModelingCapabilities,
    ModelingExecutionResult,
    ModelingModelVersion,
    ModelingPlan,
    ModelingPrintabilityReport,
    ModelingPrintabilityRequest,
    ModelingSession,
    ModelingSessionStart,
    ModelingSnapshot,
    ModelingSnapshotCreate,
    ModelingSnapshotRestore,
    ModelingSnapshotRestoreResult,
    ModelingToolCall,
)
from app.modeling.service import get_modeling_service
from app.storage.store import get_store

router = APIRouter()


def _service():
    store = get_store()
    required = [
        "list_modeling_plans",
        "upsert_modeling_plan",
        "get_modeling_plan",
        "get_modeling_plan_by_step",
        "upsert_modeling_session",
        "upsert_modeling_snapshot",
    ]
    if not all(hasattr(store, name) for name in required):
        raise HTTPException(status_code=501, detail="Módulo 3D não suportado neste backend.")
    return get_modeling_service(store)


@router.get("/capabilities", response_model=ModelingCapabilities)
def capabilities() -> ModelingCapabilities:
    return _service().capabilities()


@router.get("/sessions", response_model=list[ModelingSession])
def list_sessions() -> list[ModelingSession]:
    store = get_store()
    if not hasattr(store, "list_modeling_sessions"):
        return []
    return store.list_modeling_sessions()


@router.post("/sessions/start", response_model=ModelingSession)
def start_session(payload: ModelingSessionStart) -> ModelingSession:
    return _service().start_session(payload)


@router.get("/plans", response_model=list[ModelingPlan])
def list_plans() -> list[ModelingPlan]:
    store = get_store()
    if not hasattr(store, "list_modeling_plans"):
        return []
    return store.list_modeling_plans()


# NOTE: ``POST /plans`` was removed in Onda 2.11 (ADR-013). Plans are now
# created exclusively by the chat-first orchestrator via the
# ``3d.propose_plan`` / ``3d.propose_edit_plan`` agent tools. External
# callers that need a plan should drive the chat instead.


@router.get("/plans/{plan_id}", response_model=ModelingPlan)
def get_plan(plan_id: str) -> ModelingPlan:
    store = get_store()
    if not hasattr(store, "get_modeling_plan"):
        raise HTTPException(status_code=501, detail="Módulo 3D não suportado neste backend.")
    plan = store.get_modeling_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.")
    return plan


@router.post("/plans/{plan_id}/approve", response_model=ModelingPlan)
def approve_plan(plan_id: str, payload: ModelingApprovalRequest) -> ModelingPlan:
    try:
        return _service().approve_plan(plan_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc


@router.post("/plans/{plan_id}/execute", response_model=ModelingExecutionResult)
def execute_plan(plan_id: str) -> ModelingExecutionResult:
    try:
        return _service().execute_plan(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plano 3D não encontrado.") from exc


# NOTE: ``POST /steps/{step_id}/approve`` was removed in Onda 2.11
# (ADR-013). Approval is now global at the plan level via the chat card;
# high-risk steps in edit plans reopen approval inline through the same
# plan-level endpoint rather than per step.


@router.get("/snapshots", response_model=list[ModelingSnapshot])
def list_snapshots(
    plan_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> list[ModelingSnapshot]:
    store = get_store()
    if not hasattr(store, "list_modeling_snapshots"):
        return []
    return store.list_modeling_snapshots(plan_id=plan_id, project_id=project_id)


@router.post("/snapshots", response_model=ModelingSnapshot)
def create_snapshot(payload: ModelingSnapshotCreate) -> ModelingSnapshot:
    return _service().create_snapshot(payload)


@router.get("/snapshots/{snapshot_id}", response_model=ModelingSnapshot)
def get_snapshot(snapshot_id: str) -> ModelingSnapshot:
    store = get_store()
    if not hasattr(store, "get_modeling_snapshot"):
        raise HTTPException(status_code=501, detail="Snapshot 3D não suportado neste backend.")
    snapshot = store.get_modeling_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot 3D não encontrado.")
    return snapshot


@router.post("/snapshots/{snapshot_id}/restore", response_model=ModelingSnapshotRestoreResult)
def restore_snapshot(
    snapshot_id: str, payload: ModelingSnapshotRestore | None = None
) -> ModelingSnapshotRestoreResult:
    try:
        return _service().restore_snapshot(snapshot_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Snapshot 3D não encontrado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tool-calls", response_model=list[ModelingToolCall])
def list_tool_calls(
    plan_id: str | None = Query(default=None),
    step_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ModelingToolCall]:
    return _service().list_tool_calls(plan_id=plan_id, step_id=step_id, limit=limit)


@router.post("/validate/printability", response_model=ModelingPrintabilityReport)
def validate_printability(payload: ModelingPrintabilityRequest) -> ModelingPrintabilityReport:
    return _service().run_printability(payload)


@router.get("/printability-reports", response_model=list[ModelingPrintabilityReport])
def list_printability_reports(
    plan_id: str | None = Query(default=None),
    file_id: str | None = Query(default=None),
) -> list[ModelingPrintabilityReport]:
    return _service().list_printability_reports(plan_id=plan_id, file_id=file_id)


@router.get("/model-versions", response_model=list[ModelingModelVersion])
def list_model_versions(project_id: str | None = Query(default=None)) -> list[ModelingModelVersion]:
    store = get_store()
    if not hasattr(store, "list_modeling_model_versions"):
        return []
    return store.list_modeling_model_versions(project_id=project_id)
