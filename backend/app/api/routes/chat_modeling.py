"""3D modeling bounded context for the chat stream.

Extracted from ``chat.py`` (architecture-map finding "monólitos de borda")
to keep the 3D flow — a separate bounded context per AGENTS.md — out of the
general chat handler. ``stream_chat`` computes the project/knowledge-base
scope and then delegates to :func:`build_modeling_3d_stream_response`.

The behaviour is unchanged from the inline version: the stream proposes a
plan in ``waiting_approval`` (ADR-013 gate) and never executes inline; the
``ModelingChatOrchestrator`` runs execution only on explicit approval via the
card endpoints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from app.api.routes.chat_sse import DEFAULT_CHAT_TITLES, _runtime_status, _sse
from app.audit.service import record_audit_event
from app.core.contracts import (
    AuditEvent,
    ChatMessage,
    ChatModelingStage,
    ChatSession,
    ChatStreamRequest,
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanStatus,
    now_utc,
)
from app.cost_governor.service import estimate_tokens
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.service import get_modeling_service


def _promote_modeling_session(
    store, session: ChatSession, payload: ChatStreamRequest
) -> ChatSession:
    if not payload.modeling_3d.enabled or session.is_modeling_3d:
        return session
    updated = session.model_copy(
        update={
            "is_modeling_3d": True,
            "modeling_software_preference": payload.modeling_3d.software_override,
            "modeling_stage": ChatModelingStage.discovery,
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    return updated


def _sync_modeling_plan_proposed(store, session: ChatSession, plan: ModelingPlan) -> ChatSession:
    """Link a freshly proposed (not yet executed) plan to the chat and move it
    to ``planning``.

    The plan is awaiting the user's decision on the ModelingPlanCard.
    Execution only happens after an explicit approval
    (``POST /api/3d/plans/{id}/approve`` + ``/execute``, driven by the
    ModelingChatOrchestrator), preserving human-in-the-loop for the primary
    plan and any high-risk step (ADR-013 / AGENTS.md).
    """

    updated = session.model_copy(
        update={
            "is_modeling_3d": True,
            "modeling_software_preference": plan.software_choice,
            "modeling_stage": ChatModelingStage.planning,
            "modeling_plan_id": plan.id,
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    return updated


def _modeling_plan_metadata(plan: ModelingPlan) -> dict[str, object]:
    return {
        "id": plan.id,
        "project_id": plan.project_id,
        "conversation_id": plan.conversation_id,
        "prompt": plan.prompt,
        "mode": plan.mode.value,
        "software_choice": plan.software_choice.value,
        "confidence": plan.confidence,
        "approval_required": plan.approval_required,
        "status": plan.status.value,
        "rationale": plan.rationale,
        "assumptions": plan.assumptions,
        "risks": plan.risks,
        "knowledge_base_ids": plan.knowledge_base_ids,
        "planner_source": plan.planner_source.value if plan.planner_source else None,
        "fallback_reason": plan.fallback_reason,
        # ``trace_id`` permite que o frontend chame
        # ``GET /api/modeling/plans/{id}/trace`` ou
        # ``GET /api/modeling/traces/{trace_id}`` ao abrir o modal de
        # diagnóstico. Lido do contextvar — None se observability
        # estiver desligada ou se o handler não passou pelo orchestrator.
        "trace_id": current_trace_id(),
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
        "steps": [
            {
                "id": step.id,
                "seq": step.seq,
                "title": step.title,
                "software": step.software.value,
                "tool_name": step.tool_name,
                "risk_level": step.risk_level.value,
                "approval_required": step.approval_required,
                "status": step.status.value,
                "input_json": step.input_json,
                "output_json": step.output_json,
                "error": step.error,
                "approved_at": step.approved_at.isoformat() if step.approved_at else None,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            }
            for step in plan.steps
        ],
    }


def _modeling_plan_chat_summary(plan: ModelingPlan) -> str:
    approval = "aguardando aprovação humana" if plan.approval_required else "sem aprovação pendente"
    planner = "IA" if plan.planner_source and plan.planner_source.value == "llm" else "heurístico"
    if plan.status.value == "completed":
        next_step = "Execução concluída. Use o painel 3D para detalhes, snapshots e printability."
    elif plan.status.value == "failed":
        next_step = "Houve falha na execução. Revise os erros no painel 3D."
    elif plan.mode == ModelingExecutionMode.plan_only:
        next_step = "Revise o card do plano e execute pelo painel 3D quando quiser continuar."
    elif plan.approval_required:
        next_step = "Revise o card do plano; só etapas destrutivas/high-risk ficam bloqueadas."
    else:
        next_step = (
            "Vou executar automaticamente as etapas allowlistadas; "
            "use o painel 3D para acompanhar detalhes."
        )
    lines = [
        "Criei um plano 3D estruturado para MCP local.",
        "",
        f"- Software: {plan.software_choice.value}",
        f"- Modo: {plan.mode.value}",
        f"- Status: {plan.status.value} ({approval})",
        f"- Planner: {planner}",
        f"- Etapas: {len(plan.steps)}",
    ]
    if plan.rationale:
        lines.extend(["", f"Racional: {plan.rationale}"])
    lines.extend(["", f"Próximo passo: {next_step}"])
    return "\n".join(lines)


def build_modeling_3d_stream_response(
    store,
    session: ChatSession,
    payload: ChatStreamRequest,
    *,
    effective_project_id: str,
    effective_context_project_ids: list[str],
    effective_knowledge_base_ids: list[str],
) -> StreamingResponse:
    """Build the SSE response for a 3D modeling turn.

    Persists the user message, proposes a plan (gated to ``waiting_approval``)
    and streams the plan card. Execution is deferred to the card endpoints.
    """

    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=payload.message,
        metadata={
            "modeling_3d": {
                "enabled": True,
                "mode": payload.modeling_3d.mode.value,
                "software_override": payload.modeling_3d.software_override.value
                if payload.modeling_3d.software_override
                else None,
            }
        },
    )
    store.add_message(user_message)
    updated_context_session = session.model_copy(
        update={
            "context_project_ids": effective_context_project_ids,
            "context_document_ids": [],
            "context_knowledge_base_ids": effective_knowledge_base_ids,
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated_context_session)
    session = updated_context_session

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="",
        metadata={
            "provider": "modeling_3d",
            "persona": "JUDITE",
            "response_mode": "modeling_3d",
        },
    )

    async def modeling_events() -> AsyncIterator[str]:
        nonlocal session
        yield _sse("meta", {"session_id": session.id, "message_id": assistant_message.id})
        yield _runtime_status(
            "modeling_3d",
            "Planejando modelo 3D",
            "Enviando o prompt ao planner MCP 3D com contexto do chat.",
        )
        modeling_service = get_modeling_service(store)

        # Inicia trace de observabilidade ANTES da chamada do planner.
        # Esta rota não passa pelo ModelingChatOrchestrator (chama o
        # service direto), então o start_trace tem que vir aqui senão
        # planner_service.record(...) cai em no-op por falta de
        # contextvar. Ver app/modeling/observability.py.
        _modeling_tracer = get_tracer(
            store if hasattr(store, "record_trace_events_bulk") else None
        )
        _modeling_tracer.start_trace(
            session_id=session.id,
            project_id=effective_project_id,
        )

        # PR#28 review (issue 2): close_trace() é chamado em TODOS os
        # exit points abaixo (early-return error paths + happy path)
        # para garantir cleanup do buffer. Sem isso o trace ficaria
        # preso indefinidamente (apenas eviccionado pelo cap FIFO).
        try:
            plan = await modeling_service.create_plan_async(
                ModelingPlanCreate(
                    prompt=payload.message,
                    project_id=effective_project_id,
                    conversation_id=session.id,
                    mode=payload.modeling_3d.mode,
                    software_override=payload.modeling_3d.software_override,
                    knowledge_base_ids=effective_knowledge_base_ids,
                )
            )
            # Flush imediato — frontend que ler /api/3d/plans/{id}/trace
            # logo após receber o SSE ``modeling_plan`` precisa ver tudo
            # já persistido (não fica em buffer).
            _modeling_tracer.flush(current_trace_id())
        except Exception as exc:  # noqa: BLE001 - stream must surface domain failures
            # Garante que o trace de erro chegue ao DB.
            _modeling_tracer.flush(current_trace_id())
            _modeling_tracer.close_trace()
            error_message = f"Não consegui criar o plano 3D via MCP: {exc}"
            assistant_message.content = error_message
            assistant_message.metadata["provider_error"] = str(exc)
            store.add_message(assistant_message)
            yield _sse("error", {"message": error_message, "reason": str(exc)})
            yield _sse("done", {"session_id": session.id, "message_id": assistant_message.id})
            return

        # ADR-013 / AGENTS.md: o plano 3D NÃO é mais executado inline no
        # stream. Forçamos ``waiting_approval`` para o ModelingPlanCard
        # exibir "Aprovar"/"Rejeitar"; a execução só roda quando o usuário
        # aprova pelo card (POST /api/3d/plans/{id}/approve + /execute),
        # ambos roteados pelo ModelingChatOrchestrator. Assim o plano
        # primário e qualquer etapa high-risk/destrutiva ficam sob gate
        # humano (preserva human-in-the-loop). A auto-execução fluida de
        # edições aditivas é trabalho separado (specs/modeling-3d-fusion).
        if plan.status not in (
            ModelingPlanStatus.waiting_approval,
            ModelingPlanStatus.completed,
            ModelingPlanStatus.failed,
            ModelingPlanStatus.rejected,
        ):
            plan = plan.model_copy(
                update={
                    "status": ModelingPlanStatus.waiting_approval,
                    "updated_at": now_utc(),
                }
            )
            if hasattr(store, "upsert_modeling_plan"):
                store.upsert_modeling_plan(plan)

        plan_metadata = _modeling_plan_metadata(plan)
        session = _sync_modeling_plan_proposed(store, session, plan)
        assistant_message.content = _modeling_plan_chat_summary(plan)
        assistant_message.metadata["modeling_plan"] = plan_metadata
        assistant_message.metadata["modeling_plan_id"] = plan.id
        store.add_message(assistant_message)
        normalized_title = (session.title or "").strip().lower()
        default_prompt_title = payload.message.strip()[:48].lower()
        if normalized_title in DEFAULT_CHAT_TITLES or not normalized_title:
            should_update_title = True
        elif (session.metadata or {}).get("is_empty_draft") is True:
            should_update_title = True
        else:
            should_update_title = normalized_title == default_prompt_title
        if should_update_title:
            title = payload.message.strip()[:72].rstrip() or "Modelagem 3D"
            session_metadata = dict(session.metadata or {})
            session_metadata["title_source"] = "modeling_3d_prompt"
            session_metadata["is_empty_draft"] = False
            titled_session = session.model_copy(
                update={"title": title, "metadata": session_metadata, "updated_at": now_utc()}
            )
            if hasattr(store, "upsert_chat_session"):
                store.upsert_chat_session(titled_session)
            yield _sse("session_title", {"session_id": session.id, "title": title})
        yield _runtime_status(
            "modeling_3d_plan",
            "Plano 3D pronto — aguardando sua aprovação",
            (
                f"{len(plan.steps)} etapas para {plan.software_choice.value}. "
                "Revise o card e clique em Aprovar para executar, ou Rejeitar "
                "para refazer."
            ),
        )
        yield _sse("modeling_plan", {"plan": plan_metadata})
        yield _sse("token", {"content": assistant_message.content})
        yield _runtime_status("done", "Concluído")
        record_audit_event(
            AuditEvent(
                event_type="chat.modeling_3d_plan",
                model_id=None,
                tokens_in=estimate_tokens(payload.message),
                tokens_out=estimate_tokens(assistant_message.content),
                estimated_cost_brl=0,
                metadata={
                    "session_id": session.id,
                    "plan_id": plan.id,
                    "project_id": effective_project_id,
                    "context_project_ids": effective_context_project_ids,
                    "context_knowledge_base_ids": effective_knowledge_base_ids,
                    "software": plan.software_choice.value,
                    "mode": plan.mode.value,
                    "planner_source": plan.planner_source.value
                    if plan.planner_source
                    else None,
                },
            )
        )
        yield _sse("done", {"session_id": session.id, "message_id": assistant_message.id})
        # PR#28 review (issue 2): cleanup do buffer no happy path.
        _modeling_tracer.close_trace()

    return StreamingResponse(modeling_events(), media_type="text/event-stream")


__all__ = [
    "_modeling_plan_chat_summary",
    "_modeling_plan_metadata",
    "_promote_modeling_session",
    "_sync_modeling_plan_proposed",
    "build_modeling_3d_stream_response",
]
