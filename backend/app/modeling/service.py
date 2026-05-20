"""Facade over the focused modeling services.

ADR-013 split the v1 monolithic ``ModelingService`` (~950 lines) into five
focused services living in their own modules:

* :class:`app.modeling.planner_service.ModelingPlannerService`
* :class:`app.modeling.executor.ModelingExecutorService`
* :class:`app.modeling.snapshot_service.ModelingSnapshotService`
* :class:`app.modeling.artifacts.ModelingArtifactService`
* :class:`app.modeling.printability.ModelingPrintabilityService`

This module keeps :class:`ModelingService` as a thin facade so that all
existing imports (``from app.modeling.service import ModelingService``)
and method signatures keep working. New callers are encouraged to import
the focused service they actually need.

Legacy re-exports (``ARTIFACT_CONTENT_TYPES``, ``_envelope_into_output``,
``_envelope_from_output``) are kept for backwards compatibility.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import (
    AuditEvent,
    ModelingApprovalDecision,
    ModelingApprovalRequest,
    ModelingCapabilities,
    ModelingCapability,
    ModelingDiscoveryAssessment,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanStatus,
    ModelingPrintabilityReport,
    ModelingPrintabilityRequest,
    ModelingSession,
    ModelingSessionStart,
    ModelingSnapshot,
    ModelingSnapshotCreate,
    ModelingSnapshotRestore,
    ModelingSnapshotRestoreResult,
    ModelingStepStatus,
    ModelingToolCall,
    now_utc,
)
from app.llm_gateway.gateway import LLMGateway
from app.modeling.artifacts import ARTIFACT_CONTENT_TYPES, ModelingArtifactService
from app.modeling.executor import (
    ModelingExecutorService,
)
from app.modeling.executor import (
    envelope_from_output as _envelope_from_output,
)
from app.modeling.executor import (
    envelope_into_output as _envelope_into_output,
)
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.planner_service import ModelingPlannerService
from app.modeling.printability import ModelingPrintabilityService
from app.modeling.snapshot_service import ModelingSnapshotService


class ModelingService:
    """Thin facade composed of focused services.

    Public methods preserve the v1 signatures; internally each call
    delegates to the matching service.
    """

    def __init__(
        self,
        store: Any,
        mcp_client: LocalMCPClient | None = None,
        gateway: LLMGateway | None = None,
    ) -> None:
        self.store = store
        self.mcp_client = mcp_client or LocalMCPClient()
        self.gateway = gateway or LLMGateway()

        # Compose focused services (each takes only the collaborators it needs).
        self.planner = ModelingPlannerService(store=store, gateway=self.gateway)
        self.snapshots = ModelingSnapshotService(store=store)
        self.artifacts = ModelingArtifactService(store=store)
        self.executor = ModelingExecutorService(
            store=store,
            mcp_client=self.mcp_client,
            snapshots=self.snapshots,
            artifacts=self.artifacts,
        )
        self.printability = ModelingPrintabilityService(
            store=store, mcp_client=self.mcp_client
        )

    # ------------------------------------------------------------------
    # capabilities & sessions
    # ------------------------------------------------------------------

    def capabilities(self) -> ModelingCapabilities:
        capabilities = self.mcp_client.capabilities()
        return ModelingCapabilities(
            safety_notes=[
                "MCP roda localmente; nenhum MCP remoto fica exposto no MVP.",
                (
                    "Adições e alterações normais autoexecutam; deleções, "
                    "ações destrutivas e high-risk exigem aprovação."
                ),
                "Scripts livres e comandos de shell ficam bloqueados até revisão explícita.",
            ],
            adapters=[
                ModelingCapability(
                    software=software,
                    connected=self.mcp_client.is_connected(software),
                    transport=self.mcp_client.transport(software),
                    tools=tools,
                    status=self.mcp_client.adapter_status(software),
                    detail=self.mcp_client.detail(software),
                )
                for software, tools in capabilities.items()
            ],
        )

    def start_session(self, payload: ModelingSessionStart) -> ModelingSession:
        session = ModelingSession(
            software=payload.software,
            project_id=payload.project_id,
            status="mock" if payload.force_mock else "starting",
            mcp_server=f"{payload.software.value}_mcp",
            metadata={
                "force_mock": payload.force_mock,
                "requires_desktop_adapter": True,
            },
        )
        self.store.upsert_modeling_session(session)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.session_started",
                metadata={
                    "session_id": session.id,
                    "software": session.software.value,
                    "status": session.status,
                },
            ),
        )
        return session

    # ------------------------------------------------------------------
    # planner (delegated)
    # ------------------------------------------------------------------

    def create_plan(self, payload: ModelingPlanCreate) -> ModelingPlan:
        return self.planner.create_plan(payload)

    async def create_plan_async(self, payload: ModelingPlanCreate) -> ModelingPlan:
        return await self.planner.create_plan_async(payload)

    async def assess_request_async(
        self,
        prompt: str,
        *,
        history: list[dict[str, str]] | None = None,
        software_override: Any = None,
        threshold: float | None = None,
    ) -> ModelingDiscoveryAssessment:
        """P2 discovery: avalia se o pedido está pronto para planejar."""

        return await self.planner.assess_request_async(
            prompt,
            history=history,
            software_override=software_override,
            threshold=threshold,
        )

    # ------------------------------------------------------------------
    # approval & step decisions (kept inline; mutate only the persisted plan)
    # ------------------------------------------------------------------

    def approve_plan(
        self, plan_id: str, payload: ModelingApprovalRequest
    ) -> ModelingPlan:
        plan = self._get_plan_or_raise(plan_id)
        if payload.decision == ModelingApprovalDecision.reject:
            rejected = plan.model_copy(
                update={"status": ModelingPlanStatus.rejected, "updated_at": now_utc()}
            )
            self.store.upsert_modeling_plan(rejected)
            return rejected

        steps = [
            step.model_copy(
                update={
                    "status": ModelingStepStatus.approved
                    if step.approval_required
                    else step.status,
                    "approved_at": now_utc() if step.approval_required else step.approved_at,
                }
            )
            for step in plan.steps
        ]
        approved = plan.model_copy(
            update={
                "status": ModelingPlanStatus.approved,
                "steps": steps,
                "updated_at": now_utc(),
            }
        )
        self.store.upsert_modeling_plan(approved)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_approved",
                metadata={"plan_id": approved.id, "reason": payload.reason},
            ),
        )
        return approved

    def decide_step(
        self, step_id: str, payload: ModelingApprovalRequest
    ) -> ModelingPlan:
        plan = self.store.get_modeling_plan_by_step(step_id)
        if plan is None:
            raise KeyError(step_id)
        next_steps = []
        for step in plan.steps:
            if step.id != step_id:
                next_steps.append(step)
                continue
            if payload.decision == ModelingApprovalDecision.reject:
                next_steps.append(
                    step.model_copy(
                        update={
                            "status": ModelingStepStatus.rejected,
                            "error": payload.reason or "Etapa rejeitada pelo usuário.",
                        }
                    )
                )
            else:
                next_steps.append(
                    step.model_copy(
                        update={
                            "status": ModelingStepStatus.approved,
                            "approved_at": now_utc(),
                        }
                    )
                )
        status = (
            ModelingPlanStatus.rejected
            if any(step.status == ModelingStepStatus.rejected for step in next_steps)
            else plan.status
        )
        updated = plan.model_copy(
            update={"steps": next_steps, "status": status, "updated_at": now_utc()}
        )
        self.store.upsert_modeling_plan(updated)
        return updated

    # ------------------------------------------------------------------
    # execution (delegated)
    # ------------------------------------------------------------------

    def execute_plan(self, plan_id: str) -> ModelingExecutionResult:
        plan = self._get_plan_or_raise(plan_id)
        return self.executor.execute_plan(plan)

    # ------------------------------------------------------------------
    # snapshots (delegated)
    # ------------------------------------------------------------------

    def create_snapshot(self, payload: ModelingSnapshotCreate) -> ModelingSnapshot:
        return self.snapshots.create(payload)

    def restore_snapshot(
        self,
        snapshot_id: str,
        payload: ModelingSnapshotRestore | None = None,
    ) -> ModelingSnapshotRestoreResult:
        return self.snapshots.restore(snapshot_id, payload)

    # ------------------------------------------------------------------
    # tool calls
    # ------------------------------------------------------------------

    def list_tool_calls(
        self,
        *,
        plan_id: str | None = None,
        step_id: str | None = None,
        limit: int = 200,
    ) -> list[ModelingToolCall]:
        if not hasattr(self.store, "list_modeling_tool_calls"):
            return []
        return self.store.list_modeling_tool_calls(
            plan_id=plan_id, step_id=step_id, limit=limit
        )

    # ------------------------------------------------------------------
    # printability (delegated)
    # ------------------------------------------------------------------

    def run_printability(
        self, payload: ModelingPrintabilityRequest
    ) -> ModelingPrintabilityReport:
        return self.printability.run(payload)

    def list_printability_reports(
        self, *, plan_id: str | None = None, file_id: str | None = None
    ) -> list[ModelingPrintabilityReport]:
        return self.printability.list(plan_id=plan_id, file_id=file_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_plan_or_raise(self, plan_id: str) -> ModelingPlan:
        plan = self.store.get_modeling_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        return plan


def get_modeling_service(store: Any) -> ModelingService:
    return ModelingService(store)


__all__ = [
    "ARTIFACT_CONTENT_TYPES",
    "ModelingService",
    "_envelope_from_output",
    "_envelope_into_output",
    "get_modeling_service",
]
