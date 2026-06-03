"""Bounded context de modelagem 3D do stream de chat.

Extraído de ``chat.py`` (architecture-map "monólitos de borda"): mantém o
fluxo 3D — bounded context separado por AGENTS.md — fora do handler de chat
geral. ``stream_chat`` resolve escopo de projeto/bases e delega a
:func:`build_modeling_3d_stream_response`.

Comportamento idêntico ao fluxo inline do master (#30, P1-P5): descoberta/
edição (P2/P3), modo fluido (P3) e o plano sempre PARA em ``waiting_approval``
(gate ADR-013) — a execução só ocorre pelos endpoints do card.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from app.api.routes.chat_sse import DEFAULT_CHAT_TITLES, _runtime_status, _sse
from app.audit.service import record_audit_event
from app.core.config import settings
from app.core.contracts import (
    AuditEvent,
    ChatMessage,
    ChatModelingStage,
    ChatSession,
    ChatStreamRequest,
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanKind,
    ModelingPlanStatus,
    now_utc,
)
from app.cost_governor.service import estimate_tokens
from app.modeling.chat_orchestrator import get_modeling_orchestrator
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.planner_service import build_attachments_context
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


def _modeling_plan_metadata(plan: ModelingPlan) -> dict[str, object]:
    # Importação local para evitar ciclo (chat.py é importado cedo no app
    # startup). ``current_trace_id`` lê o contextvar bindado pelo
    # ModelingChatOrchestrator.propose_plan.
    from app.modeling.observability import current_trace_id

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
        # ``kind`` decide o card no frontend: ``edit`` → ModelingEditCard (com
        # "Desfazer última edição"); ``primary`` → ModelingPlanCard. Sem isto a
        # edição era SEMPRE desenhada como plano primário (T3.6/regressão do gate).
        "kind": plan.kind.value,
        "parent_plan_id": plan.parent_plan_id,
        "rollback_marker": plan.rollback_marker,
        # ``trace_id`` permite que o frontend chame
        # ``GET /api/3d/plans/{id}/trace`` ou
        # ``GET /api/3d/traces/{trace_id}`` ao abrir o modal de
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


def _modeling_chat_history(
    store, session_id: str, *, exclude_message: str | None = None
) -> list[dict[str, str]]:
    """Histórico user/assistant da sessão para o agente de descoberta (P2).

    ``exclude_message`` remove a última ocorrência igual ao texto do turno
    atual (que já foi persistido) para não duplicá-lo — o discovery recebe o
    prompt do turno separadamente.
    """

    history: list[dict[str, str]] = []
    if hasattr(store, "get_chat_session"):
        target_session = store.get_chat_session(session_id)
    else:
        target_session = next(
            (
                chat_session
                for chat_session in store.list_chat_sessions()
                if chat_session.id == session_id
            ),
            None,
        )
    if target_session is not None:
        for message in getattr(target_session, "messages", []) or []:
            if message.role in {"user", "assistant"} and (message.content or "").strip():
                history.append({"role": message.role, "content": message.content})
    if exclude_message is not None:
        for index in range(len(history) - 1, -1, -1):
            if history[index]["role"] == "user" and history[index]["content"] == exclude_message:
                history.pop(index)
                break
    return history


def _force_plan_new_document(store, plan: ModelingPlan) -> ModelingPlan:
    """P3: marca o primeiro ``open_design`` do plano com ``new_document=True``
    para forçar um documento limpo (caso "modelo do zero" num chat que já
    tinha modelo). O default do adapter é REUSAR o design ativo (P3a)."""

    changed = False
    steps = []
    for step in plan.steps:
        if not changed and step.tool_name.endswith("open_design"):
            new_input = dict(step.input_json or {})
            new_input["new_document"] = True
            steps.append(step.model_copy(update={"input_json": new_input}))
            changed = True
        else:
            steps.append(step)
    if not changed:
        return plan
    updated = plan.model_copy(update={"steps": steps, "updated_at": now_utc()})
    if hasattr(store, "upsert_modeling_plan"):
        store.upsert_modeling_plan(updated)
    return updated


def _format_intent_question() -> str:
    """Pergunta de desambiguação edição-vs-novo (P3)."""

    return (
        "Esse pedido é uma **edição do modelo atual** ou você quer **começar "
        "um modelo do zero** (descartando o atual)?\n\n"
        'Responda "editar" ou "novo" para eu seguir.'
    )


def _format_clarification(assessment) -> str:
    """Mensagem pt-BR com as perguntas de descoberta para o usuário."""

    questions = assessment.questions or [
        "Pode detalhar a geometria e as dimensões principais em milímetros?"
    ]
    lines = [
        "Antes de montar o plano, preciso entender melhor o que você quer modelar:",
        "",
    ]
    lines.extend(f"{i}. {question}" for i, question in enumerate(questions, start=1))
    lines.extend(
        [
            "",
            "Responda e eu proponho o plano (você ainda aprova antes de qualquer execução).",
        ]
    )
    return "\n".join(lines)


def _modeling_plan_chat_summary(plan: ModelingPlan) -> str:
    approval = (
        "aguardando sua aprovação"
        if plan.status == ModelingPlanStatus.waiting_approval
        else "aguardando aprovação humana"
        if plan.approval_required
        else "sem aprovação pendente"
    )
    planner = "IA" if plan.planner_source and plan.planner_source.value == "llm" else "heurístico"
    if plan.status.value == "completed":
        next_step = (
            "Execução concluída. Abra o diagnóstico (ícone no cabeçalho do chat 3D) "
            "para detalhes, snapshots e printability."
        )
    elif plan.status.value == "failed":
        next_step = "Houve falha na execução. Revise os erros no diagnóstico do chat 3D."
    elif plan.mode == ModelingExecutionMode.plan_only:
        next_step = "Revise o card do plano e aprove para executar quando quiser continuar."
    elif plan.approval_required:
        next_step = (
            "Revise o card e clique em Aprovar para executar (há etapas "
            "destrutivas/high-risk). Rejeitar volta para refinar o plano."
        )
    else:
        next_step = (
            "Revise o card e clique em Aprovar para eu executar as etapas, "
            "ou Rejeitar (com sua justificativa) para eu refazer o plano."
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
    """Constrói a resposta SSE de um turno de modelagem 3D (P1-P5).

    Movido do fluxo inline de ``stream_chat`` (master #30) sem alterar
    comportamento: persiste a mensagem, roda descoberta/edição (P2/P3),
    propõe o plano (gate ``waiting_approval``, ADR-013) e faz stream do card.
    A execução só ocorre pelos endpoints do card.
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
            },
            # F4 bug: a imagem sumia ao recarregar porque os anexos não eram
            # persistidos na mensagem do usuário. O bubble (app-chat.tsx) resolve
            # a imagem por attached_file_ids + platformFilesById.
            "attached_file_ids": list(payload.attached_file_ids or []),
            "attached_document_ids": list(payload.attached_document_ids or []),
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
        _modeling_tracer = get_tracer(store if hasattr(store, "record_trace_events_bulk") else None)
        _modeling_tracer.start_trace(
            session_id=session.id,
            project_id=effective_project_id,
        )

        # O bloco de descoberta/clarificação ANTERIOR ao try do orchestrator
        # também faz writes de store (upsert_chat_session/add_message/
        # record_audit_event) que podem falhar (Postgres fora/constraint). Sem
        # esta guarda, a exceção escaparia de ``modeling_events`` sem flush/
        # close do tracer (vazamento de buffer) e sem evento SSE ``error``.
        try:
            # P3: aplica o "modo fluido" enviado pelo cliente (opt-in por chat).
            if payload.modeling_3d.fluid_mode is not None and (
                session.modeling_fluid_mode != payload.modeling_3d.fluid_mode
            ):
                session = session.model_copy(
                    update={
                        "modeling_fluid_mode": payload.modeling_3d.fluid_mode,
                        "updated_at": now_utc(),
                    }
                )
                if hasattr(store, "upsert_chat_session"):
                    store.upsert_chat_session(session)

            # P2/P3 (descoberta + edição-vs-novo): antes de planejar, avalia se
            # o pedido está claro e — quando já há um modelo (estágio
            # ``editing``) — classifica intent (edit/new_model/ambiguous). Se
            # faltar contexto, faz perguntas e PARA. Se ambíguo entre editar e
            # refazer, pergunta. Falha de descoberta nunca bloqueia (heurístico
            # ready=true, intent=edit). Ver chat-flow-redesign.md (P2/P3).
            plan_prompt = payload.message
            plan_kind = ModelingPlanKind.primary
            has_existing_model = session.modeling_stage in (
                ChatModelingStage.editing,
                ChatModelingStage.failed,
            )
            # F4 (image-to-model): analisa os anexos UMA vez e injeta no prompt —
            # usado tanto pela DESCOBERTA quanto pelo PLANEJAMENTO. Antes a imagem
            # "se perdia": a descoberta perguntava às cegas e o plano a ignorava.
            # Roda em thread p/ não travar o event loop do streaming.
            if payload.attached_file_ids:
                attachments_block = await asyncio.to_thread(
                    build_attachments_context, store, list(payload.attached_file_ids)
                )
                if attachments_block:
                    plan_prompt = payload.message + "\n\n" + attachments_block
            if settings.modeling_discovery_enabled:
                history = _modeling_chat_history(
                    store, session.id, exclude_message=payload.message
                )
                assessment = await modeling_service.assess_request_async(
                    plan_prompt,
                    history=history,
                    software_override=payload.modeling_3d.software_override,
                    has_existing_model=has_existing_model,
                )
                _modeling_tracer.flush(current_trace_id())

                ambiguous_intent = has_existing_model and assessment.intent == "ambiguous"
                if not assessment.ready_to_plan or ambiguous_intent:
                    keep_stage = (
                        ChatModelingStage.editing
                        if has_existing_model
                        else ChatModelingStage.discovery
                    )
                    session = session.model_copy(
                        update={
                            "modeling_stage": keep_stage,
                            "updated_at": now_utc(),
                        }
                    )
                    if hasattr(store, "upsert_chat_session"):
                        store.upsert_chat_session(session)
                    if ambiguous_intent and assessment.ready_to_plan:
                        assistant_message.content = _format_intent_question()
                        audit_meta = {"reason": "edit_vs_new_ambiguous"}
                    else:
                        assistant_message.content = _format_clarification(assessment)
                        audit_meta = {"question_count": len(assessment.questions)}
                    assistant_message.metadata["modeling_clarification"] = {
                        "questions": assessment.questions,
                        "confidence": assessment.confidence,
                        "intent": assessment.intent,
                    }
                    store.add_message(assistant_message)
                    record_audit_event(
                        AuditEvent(
                            event_type="modeling.chat.clarification_asked",
                            model_id=None,
                            tokens_in=estimate_tokens(payload.message),
                            tokens_out=estimate_tokens(assistant_message.content),
                            estimated_cost_brl=0,
                            metadata={
                                "session_id": session.id,
                                "project_id": effective_project_id,
                                "confidence": assessment.confidence,
                                **audit_meta,
                            },
                        )
                    )
                    yield _runtime_status(
                        "modeling_3d_discovery",
                        "Preciso de mais detalhes",
                        "Respondi com uma pergunta antes de planejar.",
                    )
                    yield _sse("token", {"content": assistant_message.content})
                    yield _runtime_status("done", "Concluído")
                    yield _sse(
                        "done",
                        {"session_id": session.id, "message_id": assistant_message.id},
                    )
                    _modeling_tracer.close_trace()
                    return

                if assessment.refined_brief:
                    plan_prompt = assessment.refined_brief
                # Decide kind do plano: edição do modelo atual vs modelo novo.
                if has_existing_model and assessment.intent == "edit":
                    plan_kind = ModelingPlanKind.edit
            elif has_existing_model:
                # Discovery off: ainda assim trata follow-up como edição segura.
                plan_kind = ModelingPlanKind.edit
        except Exception as exc:  # noqa: BLE001 - stream must surface domain failures
            _modeling_tracer.flush(current_trace_id())
            _modeling_tracer.close_trace()
            error_message = f"Não consegui processar o pedido 3D: {exc}"
            assistant_message.content = error_message
            assistant_message.metadata["provider_error"] = str(exc)
            try:
                store.add_message(assistant_message)
            except Exception:  # noqa: BLE001 - best-effort persist on failure path
                pass
            yield _sse("error", {"message": error_message, "reason": str(exc)})
            yield _sse(
                "done", {"session_id": session.id, "message_id": assistant_message.id}
            )
            return

        # DT-006: a proposta de plano (primário/edição) é delegada ao
        # ModelingChatOrchestrator — fonte única da state machine (chat_state)
        # e dos eventos modeling.chat.*. A rota só cuida do streaming/mensagem/
        # título e é dona do trace (manage_trace=False). close_trace() é
        # chamado em TODOS os exit points abaixo para liberar o buffer.
        orchestrator = get_modeling_orchestrator(store)
        plan_create = ModelingPlanCreate(
            prompt=plan_prompt,
            project_id=effective_project_id,
            conversation_id=session.id,
            mode=payload.modeling_3d.mode,
            software_override=payload.modeling_3d.software_override,
            knowledge_base_ids=effective_knowledge_base_ids,
            # F4: o prompt já vem com a análise dos anexos injetada (acima), via
            # ``build_attachments_context`` — não repassa attached_file_ids aqui
            # para não re-analisar a imagem no planner_service.
        )
        try:
            if plan_kind == ModelingPlanKind.edit:
                # Edição: auto-executa por PADRÃO (decisão do dono 2026-05-25,
                # T3.4/RF-015) — só PARA no card quando houver etapa high-risk/
                # destrutiva (propose_edit_plan bloqueia isso sozinho via
                # _plan_has_high_risk, preservando P8). Sobrepõe a DT-006 (fluido
                # opt-in) apenas no caminho de EDIÇÃO; o plano PRIMÁRIO continua
                # parando no card independentemente do modeling_fluid_mode.
                outcome = await asyncio.to_thread(
                    orchestrator.propose_edit_plan,
                    session,
                    payload=plan_create,
                    fluid_mode=True,
                )
                session = outcome.chat
                plan = outcome.plan
                executed = outcome.execution is not None
            else:
                # Plano primário (inclui "modelo do zero" a partir de
                # editing/failed). propose_plan move o chat para planning via
                # chat_state e vincula o modeling_plan_id.
                session, plan = await asyncio.to_thread(
                    orchestrator.propose_plan,
                    session,
                    payload=plan_create,
                    manage_trace=False,
                )
                # P3 (fix gate 56d44c77): TODO plano primário = modelo NOVO →
                # documento NOVO. O doc do Fusion é COMPARTILHADO entre chats,
                # então um chat novo precisa de doc LIMPO; senão constrói sobre o
                # modelo do chat anterior e colide (foi o que quebrou o shell).
                # Antes só resetava "novo modelo no MESMO chat"
                # (has_existing_model) — o chat novo reusava o doc velho.
                plan = _force_plan_new_document(store, plan)
                # P1 (gate): o plano primário SEMPRE para para aprovação (mesmo
                # safe_auto sem high-risk); a execução só vem do card.
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
                executed = False
            _modeling_tracer.flush(current_trace_id())
        except Exception as exc:  # noqa: BLE001 - stream must surface domain failures
            _modeling_tracer.flush(current_trace_id())
            _modeling_tracer.close_trace()
            error_message = f"Não consegui criar o plano 3D via MCP: {exc}"
            assistant_message.content = error_message
            assistant_message.metadata["provider_error"] = str(exc)
            store.add_message(assistant_message)
            yield _sse("error", {"message": error_message, "reason": str(exc)})
            yield _sse("done", {"session_id": session.id, "message_id": assistant_message.id})
            return

        plan_metadata = _modeling_plan_metadata(plan)
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
        if executed:
            yield _runtime_status(
                "modeling_3d_plan",
                "Edição aplicada (modo fluido)",
                f"{len(plan.steps)} etapa(s) executada(s).",
            )
        else:
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
                    "planner_source": plan.planner_source.value if plan.planner_source else None,
                },
            )
        )
        yield _sse("done", {"session_id": session.id, "message_id": assistant_message.id})
        # PR#28 review (issue 2): cleanup do buffer no happy path.
        _modeling_tracer.close_trace()

    return StreamingResponse(modeling_events(), media_type="text/event-stream")
