"""Chat-first orchestrator for 3D modeling chats (ADR-013, Onda 2.4).

The v1 backend exposed a single tool ``3d.generate_plan`` invoked inline
by ``POST /api/chat/stream``. ADR-013 replaces it with five focused
operations that map 1-1 to the agent-facing tools described in
``docs/3d-mcp-modeling.md``:

* ``ask_clarification``           — agent asks the user a question during
                                    ``discovery`` without producing a
                                    plan.
* ``propose_plan``                — agent creates the primary plan and
                                    moves the chat to ``planning``.
* ``approve_plan``                — user clicks "Aprovar" on the card;
                                    chat moves through ``approved`` →
                                    ``executing`` → ``editing`` and the
                                    executor runs every step.
* ``reject_plan``                 — user clicks "Rejeitar"; chat returns
                                    to ``discovery`` with the reason
                                    recorded.
* ``propose_edit_plan``           — user sends a new message while in
                                    ``editing``; orchestrator creates a
                                    mini-plan and either auto-executes it
                                    (no high-risk steps) or surfaces it
                                    for inline approval (any high-risk
                                    step).

The orchestrator is a thin composition layer over the focused services
introduced in Onda 1.3 (``ModelingPlannerService``,
``ModelingExecutorService``). It is also the single place that emits the
``modeling.chat.*`` audit events so the chat-stream handler stays free of
state-machine logic.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.contracts import (
    AuditEvent,
    ChatModelingStage,
    ChatSession,
    ModelingApprovalDecision,
    ModelingApprovalRequest,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanKind,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelingTraceLevel,
    ModelingTraceSource,
    now_utc,
)
from app.modeling.agent_loop import run_plan_with_optional_loop
from app.modeling.chat_state import (
    ChatModelingEvent,
    transition,
)
from app.modeling.executor import ModelingExecutorService
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.planner_service import ModelingPlannerService
from app.modeling.policy import apply_plan_approval
from app.modeling.tool_registry import is_high_risk

logger = logging.getLogger(__name__)


@dataclass
class EditPlanOutcome:
    """Result of :meth:`ModelingChatOrchestrator.propose_edit_plan`.

    The edit plan **always** gets persisted. ``execution`` is non-None
    only when the orchestrator auto-executed the plan (no high-risk
    steps). When ``requires_approval`` is True, the card on the chat must
    wait for an explicit ``approve_plan`` call before anything runs.
    """

    chat: ChatSession
    plan: ModelingPlan
    execution: ModelingExecutionResult | None
    requires_approval: bool


class ModelingChatOrchestrator:
    """Compose planner + executor + state machine for chat-first 3D flow."""

    def __init__(
        self,
        store: Any,
        planner: ModelingPlannerService,
        executor: ModelingExecutorService,
    ) -> None:
        self.store = store
        self.planner = planner
        self.executor = executor
        # Tracer compartilhado — store é a sink dos eventos. Em testes a
        # store pode não ter ``record_trace_events_bulk``; o tracer aceita
        # ``None`` e vira no-op nesse caso.
        self._tracer = get_tracer(store if hasattr(store, "record_trace_events_bulk") else None)

    # ------------------------------------------------------------------
    # execution backend (linear executor × loop agêntico)
    # ------------------------------------------------------------------

    def _run_execution(self, plan: ModelingPlan) -> ModelingExecutionResult:
        """Executa um plano aprovado (loop agêntico × executor linear).

        Delegado a ``run_plan_with_optional_loop`` — fonte única compartilhada
        com ``ModelingService.execute_plan`` (card), para o loop não depender do
        caminho de execução.
        """

        return run_plan_with_optional_loop(self.executor, self.planner, plan)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def on_chat_created(self, chat: ChatSession) -> ChatSession:
        """Mark a freshly created 3D chat as being in ``discovery``.

        Non-3D chats are returned unchanged. Idempotent: calling twice on
        an already-discovery chat is a no-op.
        """

        if not chat.is_modeling_3d:
            return chat
        if chat.modeling_stage is not None:
            return chat
        next_stage = transition(chat.modeling_stage, ChatModelingEvent.CHAT_CREATED_AS_MODELING_3D)
        updated = chat.model_copy(update={"modeling_stage": next_stage, "updated_at": now_utc()})
        self.store.upsert_chat_session(updated)
        self._audit(
            "modeling.chat.discovery_started",
            chat_id=updated.id,
            stage=next_stage.value,
        )
        return updated

    # ------------------------------------------------------------------
    # discovery
    # ------------------------------------------------------------------

    def ask_clarification(self, chat: ChatSession, *, question: str) -> ChatSession:
        """Record that the agent asked a clarifying question.

        The actual user-facing message is emitted by the chat stream
        handler; this method only advances state and audit. Staying in
        ``discovery`` is the expected outcome.
        """

        self._require_modeling_chat(chat)
        next_stage = transition(chat.modeling_stage, ChatModelingEvent.CLARIFICATION_ASKED)
        updated = chat.model_copy(update={"modeling_stage": next_stage, "updated_at": now_utc()})
        self.store.upsert_chat_session(updated)
        self._audit(
            "modeling.chat.clarification_asked",
            chat_id=updated.id,
            question_preview=question[:120],
        )
        return updated

    # ------------------------------------------------------------------
    # planning (primary)
    # ------------------------------------------------------------------

    def propose_plan(
        self, chat: ChatSession, *, payload: ModelingPlanCreate, manage_trace: bool = True
    ) -> tuple[ChatSession, ModelingPlan]:
        """Create the primary plan for ``chat`` and move it to ``planning``.

        Forces ``payload.kind = primary``; the orchestrator owns this
        invariant. The chat is linked to the new plan via
        ``modeling_plan_id``.

        ``manage_trace=False`` (DT-006) lets a caller that already opened a
        trace — the live chat-stream route — drive this without the
        orchestrator starting/closing its own; events still land on the
        active trace.
        """

        self._require_modeling_chat(chat)

        # Inicia trace para este request de proposta de plano. Identifica
        # a sessão de chat e o projeto pais. O plan_id ainda não existe;
        # o planner_service vai chamar ``bind_plan`` quando souber.
        if manage_trace:
            self._tracer.start_trace(
                session_id=chat.id,
                project_id=chat.project_id,
            )

        primary_payload = payload.model_copy(
            update={
                "kind": ModelingPlanKind.primary,
                "parent_plan_id": None,
                "conversation_id": chat.id,
                "software_override": (
                    payload.software_override or chat.modeling_software_preference
                ),
            }
        )
        plan = self.planner.create_plan(primary_payload)
        next_stage = transition(chat.modeling_stage, ChatModelingEvent.PLAN_PROPOSED)
        updated = chat.model_copy(
            update={
                "modeling_stage": next_stage,
                "modeling_plan_id": plan.id,
                "updated_at": now_utc(),
            }
        )
        self.store.upsert_chat_session(updated)
        self._audit(
            "modeling.chat.plan_proposed",
            chat_id=updated.id,
            plan_id=plan.id,
            stage=next_stage.value,
            planner_source=plan.planner_source.value if plan.planner_source else None,
            fallback_reason=plan.fallback_reason,
        )
        # Flush dos eventos buffered — garante que o frontend que ler o
        # endpoint /trace logo após receber o ``modeling_plan`` SSE veja
        # tudo já persistido. PR#28 review: close_trace para liberar buffer.
        if manage_trace:
            self._tracer.flush(current_trace_id())
            self._tracer.close_trace()
        return updated, plan

    def approve_plan(
        self,
        chat: ChatSession,
        plan_id: str,
        *,
        payload: ModelingApprovalRequest | None = None,
    ) -> tuple[ChatSession, ModelingPlan, ModelingExecutionResult]:
        """User approved the primary plan via the chat card.

        Drives ``planning`` → ``approved`` → ``executing`` → ``editing``
        in a single call. Returns the final chat, the persisted plan and
        the executor result.
        """

        self._require_modeling_chat(chat)
        approval = payload or ModelingApprovalRequest(
            decision=ModelingApprovalDecision.approve, reason=""
        )

        # Inicia novo trace para a aprovação+execução. Diferente do trace
        # de ``propose_plan``, este cobre a invocação do executor e seus
        # tool calls. Vinculados pelo mesmo plan_id no banco.
        self._tracer.start_trace(
            session_id=chat.id,
            project_id=chat.project_id,
            plan_id=plan_id,
        )
        self._tracer.record(
            "executor.plan_approved",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message="Plano aprovado pelo usuário; iniciando execução",
            payload={"plan_id": plan_id, "reason": approval.reason},
        )

        chat = self._set_stage(
            chat, ChatModelingEvent.PLAN_APPROVED, audit="modeling.chat.plan_approved"
        )

        plan = self._get_plan_or_raise(plan_id)
        approved_plan = self._approve_plan_record(plan, approval)

        chat = self._set_stage(
            chat,
            ChatModelingEvent.EXECUTION_STARTED,
            audit="modeling.chat.execution_started",
            extra={"plan_id": plan_id},
        )

        execution = self._run_execution(approved_plan)
        outcome_event = (
            ChatModelingEvent.EXECUTION_FAILED
            if execution.plan.status == ModelingPlanStatus.failed
            else ChatModelingEvent.EXECUTION_COMPLETED
        )
        chat = self._set_stage(
            chat,
            outcome_event,
            audit=f"modeling.chat.{outcome_event.value}",
            extra={
                "plan_id": plan_id,
                "executed_step_ids": execution.executed_step_ids,
                "blocked_step_ids": execution.blocked_step_ids,
            },
        )

        # Resumo da execução no trace + flush imediato para o frontend
        # poder consultar /trace logo após o handler retornar.
        self._tracer.record(
            "executor.plan_finished",
            source=ModelingTraceSource.backend,
            level=(
                ModelingTraceLevel.error
                if execution.plan.status == ModelingPlanStatus.failed
                else ModelingTraceLevel.info
            ),
            message=f"Execução finalizada com status {execution.plan.status.value}",
            payload={
                "plan_id": plan_id,
                "status": execution.plan.status.value,
                "executed_step_ids": execution.executed_step_ids,
                "blocked_step_ids": execution.blocked_step_ids,
                "tool_call_ids": execution.tool_call_ids,
            },
        )
        self._tracer.flush(current_trace_id())
        self._tracer.close_trace()
        return chat, execution.plan, execution

    # ------------------------------------------------------------------
    # split approve / execute (chat-card two-call flow)
    # ------------------------------------------------------------------
    #
    # ``approve_plan`` above runs approval + execution in one shot — the
    # shape the agent-facing tools want. The in-chat card, however, keeps
    # the historical two-call contract (``POST /plans/{id}/approve`` then
    # ``POST /plans/{id}/execute`` driven by ``useModelingPlanActions``).
    # The two methods below split the same state machine so the live HTTP
    # routes can drive the orchestrator without changing the frontend.

    def approve_plan_only(
        self,
        chat: ChatSession,
        plan_id: str,
        *,
        payload: ModelingApprovalRequest | None = None,
    ) -> tuple[ChatSession, ModelingPlan]:
        """Approve the plan record and advance the chat WITHOUT executing.

        Stage-aware so the same endpoint serves both gates: a primary plan
        in ``planning`` advances to ``approved`` (``PLAN_APPROVED``); a
        high-risk edit in ``editing`` records ``EDIT_HIGH_RISK_APPROVED``
        and stays in ``editing``. Execution is deferred to
        :meth:`execute_plan`.
        """

        self._require_modeling_chat(chat)
        approval = payload or ModelingApprovalRequest(
            decision=ModelingApprovalDecision.approve, reason=""
        )
        if approval.decision != ModelingApprovalDecision.approve:
            raise ValueError(
                "approve_plan_only only accepts approve decisions; use reject() for rejections."
            )
        plan = self._get_plan_or_raise(plan_id)
        approved_plan = self._approve_plan_record(plan, approval)
        if chat.modeling_stage is ChatModelingStage.editing:
            chat = self._set_stage(
                chat,
                ChatModelingEvent.EDIT_HIGH_RISK_APPROVED,
                audit="modeling.chat.edit_high_risk_approved",
                extra={"plan_id": plan_id},
            )
        else:
            chat = self._set_stage(
                chat,
                ChatModelingEvent.PLAN_APPROVED,
                audit="modeling.chat.plan_approved",
                extra={"plan_id": plan_id},
            )
        return chat, approved_plan

    def execute_plan(
        self, chat: ChatSession, plan_id: str
    ) -> tuple[ChatSession, ModelingPlan, ModelingExecutionResult]:
        """Execute an already-approved plan and land the chat in ``editing``.

        Counterpart of :meth:`approve_plan_only`. Stage-aware: a primary
        plan in ``approved`` runs ``approved → executing → editing``; an
        edit or a retry already in ``editing`` just runs the executor and
        stays in ``editing`` (no transition). The executor still skips any
        step whose ``approval_required`` was not cleared, so high-risk
        steps never run without an explicit approval.
        """

        self._require_modeling_chat(chat)
        self._tracer.start_trace(
            session_id=chat.id,
            project_id=chat.project_id,
            plan_id=plan_id,
        )
        self._tracer.record(
            "executor.plan_approved",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message="Plano aprovado pelo usuário; iniciando execução",
            payload={"plan_id": plan_id},
        )

        plan = self._get_plan_or_raise(plan_id)
        # ADR-013 gate: never execute a plan the user hasn't approved. Guards
        # the split two-call flow against a direct ``execute`` that skips
        # ``approve_plan_only``. ``completed`` is allowed so a retry in
        # ``editing`` can re-run. See AGENTS.md "Preserve human-in-the-loop".
        if plan.status not in (ModelingPlanStatus.approved, ModelingPlanStatus.completed):
            raise ValueError(
                f"Plano {plan_id!r} não está aprovado (status={plan.status.value!r}); "
                "aprove antes de executar."
            )
        if chat.modeling_stage is ChatModelingStage.approved:
            chat = self._set_stage(
                chat,
                ChatModelingEvent.EXECUTION_STARTED,
                audit="modeling.chat.execution_started",
                extra={"plan_id": plan_id},
            )

        execution = self._run_execution(plan)

        if chat.modeling_stage is ChatModelingStage.executing:
            outcome_event = (
                ChatModelingEvent.EXECUTION_FAILED
                if execution.plan.status == ModelingPlanStatus.failed
                else ChatModelingEvent.EXECUTION_COMPLETED
            )
            chat = self._set_stage(
                chat,
                outcome_event,
                audit=f"modeling.chat.{outcome_event.value}",
                extra={
                    "plan_id": plan_id,
                    "executed_step_ids": execution.executed_step_ids,
                    "blocked_step_ids": execution.blocked_step_ids,
                },
            )

        self._tracer.record(
            "executor.plan_finished",
            source=ModelingTraceSource.backend,
            level=(
                ModelingTraceLevel.error
                if execution.plan.status == ModelingPlanStatus.failed
                else ModelingTraceLevel.info
            ),
            message=f"Execução finalizada com status {execution.plan.status.value}",
            payload={
                "plan_id": plan_id,
                "status": execution.plan.status.value,
                "executed_step_ids": execution.executed_step_ids,
                "blocked_step_ids": execution.blocked_step_ids,
                "tool_call_ids": execution.tool_call_ids,
            },
        )
        self._tracer.flush(current_trace_id())
        self._tracer.close_trace()
        return chat, execution.plan, execution

    def reject(
        self, chat: ChatSession, plan_id: str, *, reason: str = ""
    ) -> tuple[ChatSession, ModelingPlan]:
        """Reject a plan from the card, dispatching by stage.

        A high-risk edit pending in ``editing`` routes to
        :meth:`reject_edit_plan`; everything else to :meth:`reject_plan`.
        """

        self._require_modeling_chat(chat)
        if chat.modeling_stage is ChatModelingStage.editing:
            return self.reject_edit_plan(chat, plan_id, reason=reason)
        return self.reject_plan(chat, plan_id, reason=reason)

    def reject_plan(
        self,
        chat: ChatSession,
        plan_id: str,
        *,
        reason: str = "",
    ) -> tuple[ChatSession, ModelingPlan]:
        """User clicked ``Rejeitar`` on the primary plan card.

        Marks the plan rejected and returns the chat to ``discovery``.
        ``modeling_plan_id`` is cleared so a future ``propose_plan`` can
        bind a brand new primary plan.
        """

        self._require_modeling_chat(chat)
        plan = self._get_plan_or_raise(plan_id)
        rejection = ModelingApprovalRequest(decision=ModelingApprovalDecision.reject, reason=reason)
        rejected = self._approve_plan_record(plan, rejection)

        next_stage = transition(chat.modeling_stage, ChatModelingEvent.PLAN_REJECTED)
        updated = chat.model_copy(
            update={
                "modeling_stage": next_stage,
                "modeling_plan_id": None,
                "updated_at": now_utc(),
            }
        )
        self.store.upsert_chat_session(updated)
        self._audit(
            "modeling.chat.plan_rejected",
            chat_id=updated.id,
            plan_id=plan_id,
            reason=reason,
        )
        return updated, rejected

    # ------------------------------------------------------------------
    # editing (mini-plans)
    # ------------------------------------------------------------------

    def _load_parent_plan(self, plan_id: str | None) -> ModelingPlan | None:
        """Best-effort load do plano-pai (não levanta quando ausente)."""

        if not plan_id or not hasattr(self.store, "get_modeling_plan"):
            return None
        try:
            return self.store.get_modeling_plan(plan_id)
        except Exception:  # pragma: no cover - defensive
            return None

    def _read_live_timeline(
        self, *, software: ModelingSoftware | None, context_plan: ModelingPlan
    ) -> dict[str, Any] | None:
        """T3.2/T3.6: leitura best-effort da timeline do Fusion antes da edição.

        Roda ``fusion.query_timeline`` UMA vez, *fora* dos passos da edição (o
        loop agêntico nunca a vê; uma leitura que falha nunca bloqueia a
        edição). A saída alimenta tanto a reconciliação (T3.2/T3.3 — o planner
        parte do modelo real) quanto o marcador de rollback (T3.6 —
        ``timeline_count``). Retorna o dict de saída, ou ``None`` para software
        não-fusion / qualquer falha (Fusion offline, saída malformada).
        """

        if software != ModelingSoftware.fusion:
            return None
        probe = ModelingPlanStep(
            seq=1,
            title="Ler estado atual da timeline",
            software=ModelingSoftware.fusion,
            tool_name="fusion.query_timeline",
            risk_level=ModelingRiskLevel.low,
            status=ModelingStepStatus.approved,
            input_json={},
        )
        try:
            outcome = self.executor._execute_single_step(probe, plan=context_plan)
        except Exception:  # pragma: no cover - defensive: read must not block edit
            logger.warning("live timeline read raised; edit proceeds without it", exc_info=True)
            return None
        if not outcome.ok or not isinstance(outcome.output, dict):
            return None
        return self._inner_fusion_payload(outcome.output)

    @staticmethod
    def _inner_fusion_payload(output: dict[str, Any] | None) -> dict[str, Any] | None:
        """Extrai o payload real de um tool fusion do envelope do adapter.

        Tools fusion BEM-SUCEDIDAS devolvem o dict do script como JSON
        *stringificado* em ``output["message"]`` (duplicado em
        ``output["result"]["message"]``); o executor só promove os campos ao
        topo quando é FALHA (``_unwrap_inner_fusion_result``). Para ler campos
        estruturados de um sucesso (``timeline_count``, ``timeline``...) é
        preciso parsear aqui. Aceita também o formato direto (dict já plano) —
        robustez p/ mock/in_process e testes com fakes.
        """

        if not isinstance(output, dict):
            return None
        # Formato direto (mock/in_process/fakes): campos já no topo.
        if "timeline_count" in output or "timeline" in output:
            return output
        # Envelope HTTP: JSON stringificado em message / result.message.
        candidates = [output.get("message")]
        result = output.get("result")
        if isinstance(result, dict):
            candidates.append(result.get("message"))
        for cand in candidates:
            if not isinstance(cand, str):
                continue
            stripped = cand.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            try:
                inner = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(inner, dict):
                return inner
        return output

    def _apply_rollback_marker(
        self, plan: ModelingPlan, live_output: dict[str, Any] | None
    ) -> ModelingPlan:
        """T3.6: grava a contagem da timeline pré-edição em ``rollback_marker``."""

        if not isinstance(live_output, dict):
            return plan
        count = live_output.get("timeline_count")
        if not isinstance(count, int):
            return plan
        stamped = plan.model_copy(update={"rollback_marker": count})
        self.store.upsert_modeling_plan(stamped)
        return stamped

    def _build_reconciliation_block(self, live_output: dict[str, Any] | None) -> str | None:
        """T3.2/T3.3: monta o bloco ``<estado-atual-fusion>`` da leitura ao vivo.

        FACTUAL e não-alarmista de propósito: expõe a timeline + parâmetros
        REAIS como referência e instrui que, se algo divergir do histórico, o
        estado ao vivo é o atual. **NÃO** declara "edição manual" por contagem
        — passos registrados × features da timeline divergem por granularidade
        sketch/feature (seria falso positivo e empurra o planner a operações
        defensivas redundantes, ex.: um 2º fillet). A reconciliação de fato
        fica a cargo do planner (LLM).
        """

        if not isinstance(live_output, dict):
            return None
        features = live_output.get("timeline")
        count = live_output.get("timeline_count")
        if not isinstance(count, int):
            count = len(features) if isinstance(features, list) else 0
        lines = [
            "<estado-atual-fusion>",
            "Estado atual do modelo no Fusion (timeline ao vivo). Se algo aqui diferir do "
            "<modelo-atual> (histórico), considere ESTE o estado real ao planejar.",
            f"Timeline: {count} feature(s).",
        ]
        if isinstance(features, list) and features:
            named = []
            for feat in features[:40]:
                if not isinstance(feat, dict):
                    continue
                name = feat.get("name") or "?"
                ftype = feat.get("type") or ""
                label = f"{name} ({ftype})" if ftype else str(name)
                if feat.get("suppressed"):
                    label += " [suprimida]"
                named.append(label)
            if named:
                lines.append("Features: " + "; ".join(named) + ".")
        params = live_output.get("parameters")
        if isinstance(params, list) and params:
            named_p = []
            for prm in params[:20]:
                if isinstance(prm, dict) and prm.get("name"):
                    expr = prm.get("expression")
                    label = f"{prm['name']}={expr}" if expr is not None else str(prm["name"])
                    named_p.append(label)
            if named_p:
                lines.append("Parâmetros: " + ", ".join(named_p) + ".")
        lines.append("</estado-atual-fusion>")
        return "\n".join(lines)

    def propose_edit_plan(
        self, chat: ChatSession, *, payload: ModelingPlanCreate, fluid_mode: bool = True
    ) -> EditPlanOutcome:
        """Create a mini-plan for a follow-up edit in ``editing``/``failed`` stage.

        * Any high-risk step → leave the plan pending, emit
          ``EDIT_HIGH_RISK_REQUESTED``; the chat card blocks on approval.
        * Non-high-risk + ``fluid_mode`` → auto-execute immediately and
          emit ``EDIT_AUTO_EXECUTED``.
        * Non-high-risk + not ``fluid_mode`` (DT-006) → leave the plan in
          ``waiting_approval`` for the in-chat card; the chat stays in its
          current stage. Mirrors the route's opt-in fluid behavior
          (chat-flow-redesign): fluid edits are opt-in, not default.
        """

        self._require_modeling_chat(chat)
        # DT-008: aceita edições/retry tanto de ``editing`` quanto de
        # ``failed`` (uma execução que falhou pode ser corrigida pelo usuário).
        if chat.modeling_stage not in (ChatModelingStage.editing, ChatModelingStage.failed):
            raise InvalidEditStage(chat.modeling_stage)

        edit_payload = payload.model_copy(
            update={
                "kind": ModelingPlanKind.edit,
                "parent_plan_id": chat.modeling_plan_id,
                "conversation_id": chat.id,
                "software_override": (
                    payload.software_override or chat.modeling_software_preference
                ),
            }
        )
        # T3.2/T3.3 + T3.6: lê o estado atual do Fusion UMA vez, ANTES de
        # planejar. Alimenta a reconciliação (o planner parte do modelo real,
        # não do histórico desatualizado) e o marcador de rollback. Best-effort:
        # nunca bloqueia a edição (ver _read_live_timeline).
        software = edit_payload.software_override
        live_output: dict[str, Any] | None = None
        reconciliation: str | None = None
        if software == ModelingSoftware.fusion:
            parent_plan = self._load_parent_plan(chat.modeling_plan_id)
            read_context = parent_plan or ModelingPlan(
                prompt="<leitura de estado>",
                software_choice=ModelingSoftware.fusion,
                status=ModelingPlanStatus.approved,
            )
            live_output = self._read_live_timeline(software=software, context_plan=read_context)
            reconciliation = self._build_reconciliation_block(live_output)

        plan = self.planner.create_plan(edit_payload, live_state_block=reconciliation)
        plan = self._apply_rollback_marker(plan, live_output)
        high_risk = self._plan_has_high_risk(plan)

        if high_risk:
            updated = self._set_stage(
                chat,
                ChatModelingEvent.EDIT_HIGH_RISK_REQUESTED,
                audit="modeling.chat.edit_high_risk_requested",
                extra={"plan_id": plan.id},
            )
            return EditPlanOutcome(chat=updated, plan=plan, execution=None, requires_approval=True)

        if not fluid_mode:
            # DT-006: fora do modo fluido, edições não-high-risk também PARAM
            # no card (waiting_approval) em vez de auto-executar. O chat
            # permanece no estágio atual (editing/failed); a execução vem do
            # card (endpoints /approve + /execute).
            pending = plan.model_copy(
                update={"status": ModelingPlanStatus.waiting_approval, "updated_at": now_utc()}
            )
            self.store.upsert_modeling_plan(pending)
            self._audit(
                "modeling.chat.edit_approval_requested",
                chat_id=chat.id,
                plan_id=plan.id,
                stage=chat.modeling_stage.value if chat.modeling_stage else None,
            )
            return EditPlanOutcome(chat=chat, plan=pending, execution=None, requires_approval=True)

        # Auto-approve every step that the planner left as
        # ``waiting_approval`` (only a non-high-risk plan can reach this
        # branch) so the executor can run end-to-end.
        approved = self._approve_plan_record(
            plan,
            ModelingApprovalRequest(
                decision=ModelingApprovalDecision.approve,
                reason="edit_auto_approved",
            ),
        )
        execution = self._run_execution(approved)

        updated = self._set_stage(
            chat,
            ChatModelingEvent.EDIT_AUTO_EXECUTED,
            audit="modeling.chat.edit_auto_executed",
            extra={
                "plan_id": plan.id,
                "executed_step_ids": execution.executed_step_ids,
                "blocked_step_ids": execution.blocked_step_ids,
            },
        )
        return EditPlanOutcome(
            chat=updated,
            plan=execution.plan,
            execution=execution,
            requires_approval=False,
        )

    def approve_edit_plan(
        self, chat: ChatSession, plan_id: str
    ) -> tuple[ChatSession, ModelingPlan, ModelingExecutionResult]:
        """User approved a previously-pending high-risk edit plan."""

        self._require_modeling_chat(chat)
        plan = self._get_plan_or_raise(plan_id)
        approved = self._approve_plan_record(
            plan,
            ModelingApprovalRequest(
                decision=ModelingApprovalDecision.approve,
                reason="edit_high_risk_approved",
            ),
        )
        execution = self._run_execution(approved)
        updated = self._set_stage(
            chat,
            ChatModelingEvent.EDIT_HIGH_RISK_APPROVED,
            audit="modeling.chat.edit_high_risk_approved",
            extra={"plan_id": plan_id},
        )
        return updated, execution.plan, execution

    def reject_edit_plan(
        self, chat: ChatSession, plan_id: str, *, reason: str = ""
    ) -> tuple[ChatSession, ModelingPlan]:
        """User rejected a pending high-risk edit; chat returns to discovery."""

        self._require_modeling_chat(chat)
        plan = self._get_plan_or_raise(plan_id)
        rejected = self._approve_plan_record(
            plan,
            ModelingApprovalRequest(decision=ModelingApprovalDecision.reject, reason=reason),
        )
        updated = self._set_stage(
            chat,
            ChatModelingEvent.EDIT_HIGH_RISK_REJECTED,
            audit="modeling.chat.edit_high_risk_rejected",
            extra={"plan_id": plan_id, "reason": reason},
        )
        return updated, rejected

    # ------------------------------------------------------------------
    # archive
    # ------------------------------------------------------------------

    def archive_chat(self, chat: ChatSession) -> ChatSession:
        """Mark the modeling chat as ``completed`` (terminal state)."""

        if not chat.is_modeling_3d:
            return chat
        next_stage = transition(chat.modeling_stage, ChatModelingEvent.CHAT_ARCHIVED)
        updated = chat.model_copy(update={"modeling_stage": next_stage, "updated_at": now_utc()})
        self.store.upsert_chat_session(updated)
        self._audit("modeling.chat.archived", chat_id=updated.id)
        return updated

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _plan_has_high_risk(plan: ModelingPlan) -> bool:
        for step in plan.steps:
            if step.risk_level == ModelingRiskLevel.high:
                return True
            if is_high_risk(step.tool_name):
                return True
            if step.approval_required:
                return True
        return False

    def _require_modeling_chat(self, chat: ChatSession) -> None:
        if not chat.is_modeling_3d:
            raise NotAModelingChat(chat.id)

    def _get_plan_or_raise(self, plan_id: str) -> ModelingPlan:
        plan = self.store.get_modeling_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        return plan

    def _approve_plan_record(
        self, plan: ModelingPlan, payload: ModelingApprovalRequest
    ) -> ModelingPlan:
        """Aplica + persiste a decisão de aprovação e emite o audit chat-side.

        DT-006: a mutação (status do plano + promoção dos steps) vive em
        ``policy.apply_plan_approval`` — **fonte única** compartilhada com
        ``ModelingService.approve_plan``. Aqui só persistimos e emitimos o
        evento de auditoria (``modeling.plan_approved``/``_rejected``).
        """

        result = apply_plan_approval(plan, payload)
        self.store.upsert_modeling_plan(result)
        event_type = (
            "modeling.plan_rejected"
            if payload.decision == ModelingApprovalDecision.reject
            else "modeling.plan_approved"
        )
        self.store.add_audit_event(
            AuditEvent(
                event_type=event_type,
                metadata={"plan_id": result.id, "reason": payload.reason},
            ),
        )
        return result

    def _set_stage(
        self,
        chat: ChatSession,
        event: ChatModelingEvent,
        *,
        audit: str,
        extra: dict[str, Any] | None = None,
    ) -> ChatSession:
        next_stage = transition(chat.modeling_stage, event)
        updated = chat.model_copy(update={"modeling_stage": next_stage, "updated_at": now_utc()})
        self.store.upsert_chat_session(updated)
        metadata = {"chat_id": updated.id, "stage": next_stage.value}
        if extra:
            metadata.update(extra)
        self._audit(audit, **metadata)
        return updated

    def _audit(self, event_type: str, **metadata: Any) -> None:
        # Anexa trace_id do contexto ativo (se houver) para permitir
        # navegação bidirecional audit ↔ trace. Eventos âncora como
        # ``modeling.chat.plan_proposed`` ficam então cross-referenciáveis
        # com a trilha completa de debug em modeling_trace_events.
        self.store.add_audit_event(
            AuditEvent(
                event_type=event_type,
                metadata=metadata,
                trace_id=current_trace_id(),
            ),
        )


# ---------------------------------------------------------------------------
# helpers / exceptions
# ---------------------------------------------------------------------------


class NotAModelingChat(ValueError):
    """Raised when an orchestrator method is called on a non-3D chat."""

    def __init__(self, chat_id: str) -> None:
        super().__init__(f"Chat {chat_id!r} is not a modeling-3D chat.")
        self.chat_id = chat_id


class InvalidEditStage(ValueError):
    """Raised when :meth:`propose_edit_plan` is called outside ``editing``."""

    def __init__(self, stage: ChatModelingStage | None) -> None:
        stage_str = stage.value if stage is not None else "<none>"
        super().__init__(
            f"propose_edit_plan requires modeling_stage in ('editing', 'failed'), "
            f"got {stage_str!r}."
        )
        self.stage = stage


def get_modeling_orchestrator(store: Any) -> ModelingChatOrchestrator:
    """Compose the orchestrator with the same collaborators as
    :class:`app.modeling.service.ModelingService`.

    Used by the live HTTP routes (chat-stream gate + ``/plans/{id}/approve``
    + ``/plans/{id}/execute``) so the chat-first state machine and the
    ``modeling.chat.*`` audit trail are driven from one place instead of
    being bypassed (see architecture-map finding "código morto no caminho
    live"). Imports are local to avoid import cycles with ``service.py``.
    """

    from app.llm_gateway.gateway import LLMGateway
    from app.modeling.artifacts import ModelingArtifactService
    from app.modeling.mcp_client import LocalMCPClient
    from app.modeling.snapshot_service import ModelingSnapshotService

    gateway = LLMGateway()
    mcp_client = LocalMCPClient()
    snapshots = ModelingSnapshotService(store=store)
    artifacts = ModelingArtifactService(store=store)
    planner = ModelingPlannerService(store=store, gateway=gateway)
    executor = ModelingExecutorService(
        store=store,
        mcp_client=mcp_client,
        snapshots=snapshots,
        artifacts=artifacts,
    )
    return ModelingChatOrchestrator(store=store, planner=planner, executor=executor)


__all__ = [
    "EditPlanOutcome",
    "InvalidEditStage",
    "ModelingChatOrchestrator",
    "NotAModelingChat",
    "get_modeling_orchestrator",
]
