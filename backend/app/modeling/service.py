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
    ModelingPlanEdit,
    ModelingPlanKind,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingPrintabilityReport,
    ModelingPrintabilityRequest,
    ModelingRiskLevel,
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
from app.modeling.agent_loop import run_plan_with_optional_loop
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
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.planner_service import ModelingPlannerService
from app.modeling.policy import apply_modeling_policy, apply_plan_approval
from app.modeling.printability import ModelingPrintabilityService
from app.modeling.snapshot_service import ModelingSnapshotService
from app.modeling.tool_registry import PLANNER_TOOLSET


class ModelingPlanNotEditable(Exception):
    """Plano não pode ser editado no estado atual (já aprovado/executado)."""

    def __init__(self, plan_id: str, status: ModelingPlanStatus) -> None:
        super().__init__(f"Plano {plan_id!r} não é editável no estado {status.value!r}.")
        self.plan_id = plan_id
        self.status = status


class ModelingInvalidEditTool(Exception):
    """Etapa editada referencia um tool fora da allowlist do planner."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Ferramenta não permitida na edição: {tool_name!r}.")
        self.tool_name = tool_name


class ModelingPlanNotApprovable(Exception):
    """Decisão de aprovação sobre um plano em estado terminal/em execução.

    Gate anti-replay (C5 da varredura 2026-06-10): um card antigo no histórico
    do chat não pode re-aprovar um plano que já rodou (``completed``/``failed``/
    ``running``) nem ressuscitar um plano ``rejected``. A rota mapeia para 409.
    """

    def __init__(self, plan_id: str, status: ModelingPlanStatus) -> None:
        super().__init__(
            f"Plano {plan_id!r} não aceita decisão de aprovação no estado {status.value!r}."
        )
        self.plan_id = plan_id
        self.status = status


class ModelingPlanNotExecutable(Exception):
    """Execução solicitada para um plano fora dos estados executáveis.

    Gate de aprovação no endpoint do card (ADR-013 / RF-008): só executa
    plano ``approved`` (primeira execução), ``failed`` (retry explícito),
    ``running`` (retomada após queda de conexão — o frontend reconcilia) ou
    ``draft`` (no-op "modo planejamento" do executor).
    ``waiting_approval``/``rejected``/``completed`` → 409.
    """

    def __init__(self, plan_id: str, status: ModelingPlanStatus) -> None:
        super().__init__(f"Plano {plan_id!r} não é executável no estado {status.value!r}.")
        self.plan_id = plan_id
        self.status = status


class ModelingRollbackUnavailable(Exception):
    """Plano de edição sem ponto de rollback (timeline pré-edição não capturada).

    Lançada por :meth:`ModelingService.rollback_last_edit` quando
    ``plan.rollback_marker is None`` — a leitura best-effort da timeline
    falhou (Fusion offline no momento da edição) ou o software não tem
    timeline. A rota mapeia para 409.
    """

    def __init__(self, plan_id: str) -> None:
        super().__init__(
            f"Edição {plan_id!r} não tem ponto de rollback registrado "
            "(timeline pré-edição não capturada)."
        )
        self.plan_id = plan_id


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
        self.printability = ModelingPrintabilityService(store=store, mcp_client=self.mcp_client)

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
        has_existing_model: bool = False,
    ) -> ModelingDiscoveryAssessment:
        """P2/P3 discovery: avalia prontidão e intent (edit/new_model)."""

        return await self.planner.assess_request_async(
            prompt,
            history=history,
            software_override=software_override,
            threshold=threshold,
            has_existing_model=has_existing_model,
        )

    # ------------------------------------------------------------------
    # approval & step decisions (kept inline; mutate only the persisted plan)
    # ------------------------------------------------------------------

    _APPROVABLE_STATUSES = frozenset(
        {
            ModelingPlanStatus.draft,
            ModelingPlanStatus.waiting_approval,
            ModelingPlanStatus.approved,  # idempotente
            ModelingPlanStatus.rejected,  # re-rejeição idempotente (só p/ reject)
        }
    )

    def approve_plan(self, plan_id: str, payload: ModelingApprovalRequest) -> ModelingPlan:
        # DT-006: mutação de aprovação centralizada em ``policy.apply_plan_approval``
        # (fonte única compartilhada com o ModelingChatOrchestrator).
        plan = self._get_plan_or_raise(plan_id)
        if plan.status not in self._APPROVABLE_STATUSES:
            raise ModelingPlanNotApprovable(plan_id, plan.status)
        if (
            plan.status == ModelingPlanStatus.rejected
            and payload.decision != ModelingApprovalDecision.reject
        ):
            # RF-007: plano rejeitado volta para a descoberta/replanejamento;
            # um card antigo não pode ressuscitá-lo como aprovado.
            raise ModelingPlanNotApprovable(plan_id, plan.status)
        result = apply_plan_approval(plan, payload)
        self.store.upsert_modeling_plan(result)
        if payload.decision != ModelingApprovalDecision.reject:
            self.store.add_audit_event(
                AuditEvent(
                    event_type="modeling.plan_approved",
                    metadata={"plan_id": result.id, "reason": payload.reason},
                ),
            )
        return result

    def edit_plan(self, plan_id: str, payload: ModelingPlanEdit) -> ModelingPlan:
        """P4: edita um plano ANTES da aprovação (etapas e/ou rationale).

        Permitido só enquanto ``draft``/``waiting_approval``. Valida cada
        ``tool_name`` contra a allowlist do planner, reordena ``seq`` pela
        posição, re-aplica a policy de segurança e mantém o plano em
        ``waiting_approval`` (gate da P1) para o card seguir exibindo Aprovar.
        Ver specs/005-modeling-3d-fusion/chat-flow-redesign.md (P4).
        """

        plan = self._get_plan_or_raise(plan_id)
        if plan.status not in {
            ModelingPlanStatus.draft,
            ModelingPlanStatus.waiting_approval,
        }:
            raise ModelingPlanNotEditable(plan_id, plan.status)

        updates: dict[str, Any] = {"updated_at": now_utc()}
        if payload.rationale is not None:
            updates["rationale"] = payload.rationale
        if payload.steps is not None:
            existing_by_id = {step.id: step for step in plan.steps}
            new_steps: list[ModelingPlanStep] = []
            for index, edit in enumerate(payload.steps, start=1):
                if edit.tool_name not in PLANNER_TOOLSET:
                    raise ModelingInvalidEditTool(edit.tool_name)
                base = existing_by_id.get(edit.id) if edit.id else None
                if base is not None:
                    new_steps.append(
                        base.model_copy(
                            update={
                                "seq": index,
                                "title": edit.title,
                                "tool_name": edit.tool_name,
                                "risk_level": edit.risk_level,
                                "input_json": edit.input_json,
                                "status": ModelingStepStatus.pending,
                                "output_json": {},
                                "error": None,
                                "approved_at": None,
                                "completed_at": None,
                            }
                        )
                    )
                else:
                    new_steps.append(
                        ModelingPlanStep(
                            seq=index,
                            title=edit.title,
                            software=plan.software_choice,
                            tool_name=edit.tool_name,
                            risk_level=edit.risk_level,
                            input_json=edit.input_json,
                        )
                    )
            updates["steps"] = new_steps

        edited = apply_modeling_policy(plan.model_copy(update=updates))
        # Mantém o gate da P1: a policy pode ter promovido para ``approved``
        # (sem high-risk); forçamos waiting_approval para o card continuar.
        if edited.status == ModelingPlanStatus.approved:
            edited = edited.model_copy(update={"status": ModelingPlanStatus.waiting_approval})
        self.store.upsert_modeling_plan(edited)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_edited",
                metadata={"plan_id": edited.id, "step_count": len(edited.steps)},
            ),
        )
        return edited

    def decide_step(self, step_id: str, payload: ModelingApprovalRequest) -> ModelingPlan:
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

    _EXECUTABLE_STATUSES = frozenset(
        {
            ModelingPlanStatus.approved,
            ModelingPlanStatus.failed,  # retry explícito do card
            ModelingPlanStatus.running,  # retomada após queda de conexão
            # draft (plan_only) segue permitido: o executor bloqueia todos os
            # steps e devolve o no-op "modo planejamento" (contrato existente).
            ModelingPlanStatus.draft,
        }
    )

    def execute_plan(self, plan_id: str) -> ModelingExecutionResult:
        plan = self._get_plan_or_raise(plan_id)
        # Gate de aprovação no endpoint do card (ADR-013/RF-008): plano
        # ``waiting_approval``/``rejected`` não executa sem aprovação e plano
        # ``completed`` não re-executa (anti-replay, C5 da varredura).
        if plan.status not in self._EXECUTABLE_STATUSES:
            raise ModelingPlanNotExecutable(plan_id, plan.status)
        # O card (routes/modeling.py → /plans/{id}/execute) executa FORA de um
        # trace aberto. Sem isto, todo ``self._tracer.record(...)`` do executor
        # e do loop vira no-op (observability.record: ``tid is None`` → None) e o
        # diagnóstico do plano fica vazio mesmo com os tool calls persistidos.
        # Abrimos um trace ligado ao plano quando não há um ativo; se já houver
        # (fluxo de chat), só ligamos o plano e deixamos o dono fechá-lo.
        owns_trace = current_trace_id() is None
        tracer = get_tracer(self.store if hasattr(self.store, "record_trace_events_bulk") else None)
        if owns_trace:
            tracer.start_trace(plan_id=plan.id)
        else:
            tracer.bind_plan(plan.id)
        try:
            # Loop agêntico quando a flag está ligada, senão executor linear
            # (mesma fonte única do orchestrator — o card não pode ficar de fora).
            return run_plan_with_optional_loop(self.executor, self.planner, plan)
        finally:
            if owns_trace:
                tracer.close_trace()

    def rollback_last_edit(self, plan_id: str) -> ModelingExecutionResult:
        """T3.6: reverte uma edição revertendo a timeline do Fusion.

        Lê ``plan.rollback_marker`` (contagem da timeline ANTES da edição,
        capturada best-effort pelo orchestrator em ``propose_edit_plan``) e
        executa um plano de UM passo ``fusion.rollback_timeline``. Sem
        marcador → :class:`ModelingRollbackUnavailable`.

        O clique no botão "Desfazer última edição" é a aprovação humana (P6)
        desta deleção; por isso o passo nasce ``approved``. O loop agêntico é
        DELIBERADAMENTE evitado (executor linear direto): rollback é
        destrutivo e não deve ser "corrigido" automaticamente.
        """

        plan = self._get_plan_or_raise(plan_id)
        if plan.rollback_marker is None:
            raise ModelingRollbackUnavailable(plan_id)

        rollback_plan = self._build_rollback_plan(plan)
        self.store.upsert_modeling_plan(rollback_plan)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_rollback_requested",
                metadata={
                    "plan_id": rollback_plan.id,
                    "reverts_plan_id": plan.id,
                    "target_count": plan.rollback_marker,
                },
            ),
        )
        # Mesmo cuidado de trace do execute_plan: o endpoint roda fora de um
        # trace aberto, então abrimos um ligado ao plano de rollback.
        owns_trace = current_trace_id() is None
        tracer = get_tracer(self.store if hasattr(self.store, "record_trace_events_bulk") else None)
        if owns_trace:
            tracer.start_trace(plan_id=rollback_plan.id)
        else:
            tracer.bind_plan(rollback_plan.id)
        try:
            return self.executor.execute_plan(rollback_plan)
        finally:
            if owns_trace:
                tracer.close_trace()

    def _build_rollback_plan(self, edit_plan: ModelingPlan) -> ModelingPlan:
        """Monta o plano de 1 passo que reverte ``edit_plan`` via timeline."""

        step = ModelingPlanStep(
            seq=1,
            title="Reverter última edição",
            software=edit_plan.software_choice,
            tool_name="fusion.rollback_timeline",
            risk_level=ModelingRiskLevel.high,
            approval_required=False,  # aprovação = clique no botão (ver rollback_last_edit)
            status=ModelingStepStatus.approved,
            input_json={"target_count": edit_plan.rollback_marker},
        )
        return ModelingPlan(
            project_id=edit_plan.project_id,
            conversation_id=edit_plan.conversation_id,
            prompt=f"Reverter edição {edit_plan.id}",
            software_choice=edit_plan.software_choice,
            kind=ModelingPlanKind.edit,
            parent_plan_id=edit_plan.parent_plan_id or edit_plan.id,
            status=ModelingPlanStatus.approved,
            rationale="Rollback da última edição (timeline → contagem pré-edição).",
            steps=[step],
        )

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
        return self.store.list_modeling_tool_calls(plan_id=plan_id, step_id=step_id, limit=limit)

    # ------------------------------------------------------------------
    # printability (delegated)
    # ------------------------------------------------------------------

    def run_printability(self, payload: ModelingPrintabilityRequest) -> ModelingPrintabilityReport:
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
