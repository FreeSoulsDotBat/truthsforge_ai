from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.routes.chat_context import (
    _indexed_documents_for_projects,
    _knowledge_base_ids_for_runtime,
    _mentioned_folder_ids,
    _normalize_knowledge_base_ids,
    _search_knowledge_base_context,
    _select_context_documents,
)
from app.api.routes.chat_images import save_generated_images_from_markdown
from app.api.routes.chat_modeling import (
    _promote_modeling_session,
    build_modeling_3d_stream_response,
)
from app.api.routes.chat_scope import (
    _general_project_id,
    _normalize_project_ids,
    _runtime_allowed_project_ids,
    _validate_active_project_scope,
    _validate_attachment_project_scope,
)
from app.api.routes.chat_sse import DEFAULT_CHAT_TITLES, _runtime_status, _sse
from app.audit.service import record_audit_event
from app.chat.session_cleanup import (
    delete_chat_session_with_files,
    session_related_file_ids,
)
from app.core.config import settings
from app.core.contracts import (
    Agent,
    AuditEvent,
    ChatAttachmentAnalyzeRequest,
    ChatAttachmentAnalyzeResponse,
    ChatMessage,
    ChatSession,
    ChatSessionContextUpdate,
    ChatSessionCreate,
    ChatSessionDeleteResult,
    ChatSessionMoveRequest,
    ChatSessionWithMessages,
    ChatStreamRequest,
    ModelCapability,
    PlatformFile,
    PlatformFileUpdate,
    ProviderName,
    now_utc,
)
from app.cost_governor.service import (
    estimate_cost,
    estimate_tokens,
    has_configured_pricing,
    monthly_events_for_store,
    monthly_spend,
)
from app.files.processor import read_text_preview
from app.judite.orchestrator import judite_dev_response
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.model_registry import ModelRegistry
from app.llm_gateway.providers import (
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderStreamEvent,
    token_event,
)
from app.modeling.attachment_analyzer import ModelingAttachmentAnalyzer
from app.rag.indexing import ensure_document_for_platform_file
from app.storage.store import get_store
from app.workers.index_queue import enqueue_platform_file_index

router = APIRouter()
IMAGE_GENERATION_ESTIMATED_OUTPUT_TOKENS = 1290
USD_TO_BRL = 5.0


def _is_empty_draft_session(session: ChatSession) -> bool:
    metadata = session.metadata if isinstance(session.metadata, dict) else {}
    return bool(metadata.get("is_empty_draft"))


def _clear_empty_draft_flag(store, session: ChatSession) -> ChatSession:
    if not _is_empty_draft_session(session):
        return session
    metadata = dict(session.metadata or {})
    metadata["is_empty_draft"] = False
    updated = session.model_copy(update={"metadata": metadata, "updated_at": now_utc()})
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    return updated


def _apply_stream_title_to_session(
    store,
    session: ChatSession,
    payload: ChatStreamRequest,
    *,
    require_title: bool,
) -> ChatSession:
    """Persist the title collected by the Onda 5 modal for draft sessions."""

    current_title = (session.title or "").strip().lower()
    payload_title = (payload.title or "").strip()
    payload_title_valid = bool(payload_title) and payload_title.lower() not in DEFAULT_CHAT_TITLES

    if require_title and _is_empty_draft_session(session) and not payload_title_valid:
        _enforce_required_chat_title(payload)

    should_update_title = payload_title_valid and (
        _is_empty_draft_session(session)
        or not current_title
        or current_title in DEFAULT_CHAT_TITLES
    )
    if not should_update_title:
        return session

    metadata = dict(session.metadata or {})
    metadata["title_source"] = "manual"
    updated = session.model_copy(
        update={"title": payload_title, "metadata": metadata, "updated_at": now_utc()}
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    return updated


def _enforce_required_chat_title(payload: ChatStreamRequest) -> None:
    """Reject the first turn of a new chat when title is missing or default.

    Controlled by ``settings.require_chat_title`` so the legacy frontend
    keeps working until the Onda 5 UI ships. When enabled, the React
    modal must send ``payload.title`` with a user-typed value; otherwise
    the backend responds with ``HTTP 422`` and a clear error code.
    """

    raw = payload.title
    normalized = (raw or "").strip().lower()
    if not normalized or normalized in DEFAULT_CHAT_TITLES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "chat_title_required",
                "message": (
                    "Esse chat precisa de um título antes da primeira mensagem. "
                    "Renomeie o chat e envie de novo."
                ),
            },
        )


def select_orchestration_agents(
    agents: list[Agent],
    selected_agent_id: str | None,
    requested_agent_ids: list[str],
    multi_agent_mode: bool,
) -> tuple[Agent | None, Agent | None, list[Agent]]:
    agent_by_id = {agent.id: agent for agent in agents}
    selected_agent = agent_by_id.get(selected_agent_id or "")
    fallback_agent = selected_agent or next(
        (agent for agent in agents if agent.name.upper() == "JUDITE"),
        agents[0] if agents else None,
    )
    enabled_orchestrators = [
        agent for agent in agents if agent.enabled and agent.role == "orchestrator"
    ]
    primary_agent = next(
        (
            agent
            for agent in enabled_orchestrators
            if selected_agent is not None and agent.id == selected_agent.id
        ),
        None,
    )
    if primary_agent is None:
        primary_agent = next(
            (agent for agent in enabled_orchestrators if agent.name.upper() == "JUDITE"),
            enabled_orchestrators[0] if enabled_orchestrators else fallback_agent,
        )

    target_agent = (
        selected_agent
        if selected_agent is not None
        and primary_agent is not None
        and selected_agent.id != primary_agent.id
        else None
    )
    runtime_agent_ids = list(requested_agent_ids if multi_agent_mode else [])
    if target_agent is not None and target_agent.enabled:
        runtime_agent_ids = [target_agent.id, *runtime_agent_ids]

    support_agents = []
    seen_ids: set[str] = set()
    for agent_id in runtime_agent_ids:
        agent = agent_by_id.get(agent_id)
        if (
            agent is None
            or not agent.enabled
            or agent.id == getattr(primary_agent, "id", None)
            or agent.id in seen_ids
        ):
            continue
        support_agents.append(agent)
        seen_ids.add(agent.id)
    return primary_agent, target_agent, support_agents


@router.post(
    "/sessions/{chat_id}/attachments/analyze",
    response_model=ChatAttachmentAnalyzeResponse,
)
def analyze_attachment_for_chat(
    chat_id: str, payload: ChatAttachmentAnalyzeRequest
) -> ChatAttachmentAnalyzeResponse:
    """Run the deep-analysis pipeline for an attachment in a 3D chat.

    ADR-013 (Onda 2.7): the discovery agent calls this endpoint after
    the user uploads an image or a 3D file. The response carries a
    structured analysis (vision summary for images, mesh stats from
    Blender headless for STL/OBJ/3MF/BLEND, metadata-only for STEP)
    plus a ready-to-inject ``context_text`` block for the next LLM
    turn.
    """

    store = get_store()
    chat = None
    if hasattr(store, "get_chat_session"):
        chat = store.get_chat_session(chat_id)
    if chat is None:
        # Fall back to the summary list when ``get_chat_session`` is
        # unavailable (legacy stores). Match by id only.
        chat = next(
            (item for item in store.list_chat_sessions() if item.id == chat_id),
            None,
        )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat não encontrado.")
    if not chat.is_modeling_3d:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "chat_is_not_modeling_3d",
                "message": (
                    "Análise de anexo para modelagem 3D só é aceita em chats "
                    "marcados como is_modeling_3d=true."
                ),
            },
        )

    analyzer = ModelingAttachmentAnalyzer(store=store)
    analysis = analyzer.analyze(payload.file_id)
    return ChatAttachmentAnalyzeResponse(
        file_id=analysis.file_id,
        filename=analysis.filename,
        kind=analysis.kind,
        ok=analysis.ok,
        summary=analysis.summary,
        metrics=analysis.metrics,
        suggestions=analysis.suggestions,
        error=analysis.error,
        context_text=analysis.to_context_text(),
    )


@router.get("/sessions", response_model=list[ChatSessionWithMessages])
def list_sessions(include_messages: bool = False) -> list[ChatSessionWithMessages]:
    store = get_store()
    if include_messages:
        return store.list_chat_sessions()
    if hasattr(store, "list_chat_session_summaries"):
        return store.list_chat_session_summaries()
    return [
        ChatSessionWithMessages(**session.model_dump(), messages=[])
        for session in store.list_chat_sessions()
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
def get_session(
    session_id: str, message_limit: int | None = None, message_offset: int = 0
) -> ChatSessionWithMessages:
    store = get_store()
    if hasattr(store, "get_chat_session"):
        session = store.get_chat_session(session_id)
    else:
        session = next(
            (
                chat_session
                for chat_session in store.list_chat_sessions()
                if chat_session.id == session_id
            ),
            None,
        )
    if session is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    if message_limit is not None:
        limit = max(1, min(int(message_limit), 500))
        offset = max(0, int(message_offset))
        total = len(session.messages)
        end = max(0, total - offset)
        start = max(0, end - limit)
        return session.model_copy(update={"messages": session.messages[start:end]})

    return session


@router.delete("/sessions/{session_id}", response_model=ChatSessionDeleteResult)
def delete_session(session_id: str, delete_files: bool = True) -> ChatSessionDeleteResult:
    store = get_store()
    return delete_chat_session_with_files(store, session_id, delete_files=delete_files)


@router.post("/sessions", response_model=ChatSessionWithMessages)
def create_session(payload: ChatSessionCreate) -> ChatSessionWithMessages:
    store = get_store()
    session = store.create_chat_session(payload)
    metadata = dict(session.metadata or {})
    metadata["is_empty_draft"] = True
    updated = ChatSession(
        **{
            **session.model_dump(),
            "metadata": metadata,
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    return ChatSessionWithMessages(**updated.model_dump(), messages=session.messages)


def _sync_session_assets_scope(
    store,
    *,
    session: ChatSessionWithMessages,
    project_id: str,
    folder_id: str | None,
) -> None:
    if hasattr(store, "list_platform_files") and hasattr(store, "update_platform_file"):
        related_ids = session_related_file_ids(store, session)
        for platform_file in store.list_platform_files():
            metadata = (
                dict(platform_file.metadata) if isinstance(platform_file.metadata, dict) else {}
            )
            if platform_file.id not in related_ids and metadata.get("session_id") != session.id:
                continue
            metadata["project_id"] = project_id
            metadata["folder_id"] = folder_id
            updated_file = store.update_platform_file(
                platform_file.id,
                PlatformFileUpdate(metadata=metadata),
            )
            ensure_document_for_platform_file(
                store,
                updated_file,
                project_id=project_id,
                folder_id=folder_id,
                force_status_pending=True,
            )
            enqueue_platform_file_index(updated_file.id)

    if hasattr(store, "list_documents") and hasattr(store, "update_document"):
        related_ids = session_related_file_ids(store, session)
        for document in store.list_documents():
            metadata = dict(document.metadata) if isinstance(document.metadata, dict) else {}
            file_id = metadata.get("file_id")
            if metadata.get("session_id") != session.id and (
                not isinstance(file_id, str) or file_id not in related_ids
            ):
                continue
            store.update_document(
                document.model_copy(
                    update={
                        "project_id": project_id,
                        "folder_id": folder_id,
                        "updated_at": now_utc(),
                    }
                )
            )


@router.post("/sessions/{session_id}/move", response_model=ChatSessionWithMessages)
def move_session(session_id: str, payload: ChatSessionMoveRequest) -> ChatSessionWithMessages:
    store = get_store()
    try:
        if hasattr(store, "move_chat_session"):
            moved = store.move_chat_session(session_id, payload.project_id, payload.folder_id)
        else:
            existing = (
                store.get_chat_session(session_id) if hasattr(store, "get_chat_session") else None
            )
            if existing is None:
                existing = next(
                    (item for item in store.list_chat_sessions() if item.id == session_id),
                    None,
                )
            if existing is None:
                raise HTTPException(status_code=404, detail="Sessão não encontrada.")
            moved = existing.model_copy(
                update={
                    "project_id": payload.project_id,
                    "folder_id": payload.folder_id,
                    "updated_at": now_utc(),
                }
            )
            if hasattr(store, "upsert_chat_session"):
                store.upsert_chat_session(moved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hydrated = store.get_chat_session(moved.id) if hasattr(store, "get_chat_session") else None
    if hydrated is None:
        hydrated = ChatSessionWithMessages(**moved.model_dump(), messages=[])
    _sync_session_assets_scope(
        store,
        session=hydrated,
        project_id=moved.project_id,
        folder_id=moved.folder_id,
    )
    refreshed = store.get_chat_session(moved.id) if hasattr(store, "get_chat_session") else None
    if refreshed is None:
        refreshed = ChatSessionWithMessages(**moved.model_dump(), messages=hydrated.messages)
    return refreshed


@router.put("/sessions/{session_id}/context", response_model=ChatSessionWithMessages)
def update_session_context(
    session_id: str, payload: ChatSessionContextUpdate
) -> ChatSessionWithMessages:
    store = get_store()
    session = store.get_chat_session(session_id) if hasattr(store, "get_chat_session") else None
    if session is None:
        session = next(
            (item for item in store.list_chat_sessions() if item.id == session_id),
            None,
        )
    if session is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    projects = store.list_projects() if hasattr(store, "list_projects") else []
    known_project_ids = {project.id for project in projects}
    fallback_project_id = session.project_id or _general_project_id(store)
    normalized_project_ids = _normalize_project_ids(
        payload.context_project_ids,
        fallback_project_id=fallback_project_id,
        known_project_ids=known_project_ids,
    )

    indexed_documents = (
        _indexed_documents_for_projects(store.list_documents(), set(normalized_project_ids))
        if hasattr(store, "list_documents")
        else []
    )
    selected_documents = _select_context_documents(
        documents=indexed_documents,
        selected_document_ids=payload.context_document_ids,
    )
    knowledge_bases = store.list_knowledge_bases() if hasattr(store, "list_knowledge_bases") else []
    normalized_knowledge_base_ids = _normalize_knowledge_base_ids(
        payload.context_knowledge_base_ids,
        knowledge_bases=knowledge_bases,
    )

    updated = session.model_copy(
        update={
            "context_project_ids": normalized_project_ids,
            "context_document_ids": [document.id for document in selected_documents],
            "context_knowledge_base_ids": normalized_knowledge_base_ids,
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    refreshed = store.get_chat_session(updated.id) if hasattr(store, "get_chat_session") else None
    if refreshed is not None:
        return refreshed
    return ChatSessionWithMessages(**updated.model_dump(), messages=session.messages)


def _cost_metadata(
    *,
    preflight_estimated_cost_brl: float,
    final_estimated_cost_brl: float | None = None,
    current_spend_brl: float,
    monthly_budget_brl: float,
    warn_threshold_percent: int,
    block_at_budget: bool,
) -> dict[str, object]:
    final_cost = (
        preflight_estimated_cost_brl
        if final_estimated_cost_brl is None
        else final_estimated_cost_brl
    )
    projected_spend_brl = round(current_spend_brl + final_cost, 6)
    remaining_budget_brl = round(max(monthly_budget_brl - projected_spend_brl, 0), 6)
    warn_threshold_brl = round(monthly_budget_brl * warn_threshold_percent / 100, 6)
    return {
        "preflight_estimated_cost_brl": preflight_estimated_cost_brl,
        "final_estimated_cost_brl": final_estimated_cost_brl,
        "current_month_spend_brl": current_spend_brl,
        "projected_month_spend_brl": projected_spend_brl,
        "remaining_month_budget_brl": remaining_budget_brl,
        "monthly_budget_brl": monthly_budget_brl,
        "warn_threshold_percent": warn_threshold_percent,
        "warn_threshold_brl": warn_threshold_brl,
        "block_at_budget": block_at_budget,
        "usd_to_brl": USD_TO_BRL,
    }


def _context_audit_metadata(
    *,
    project_id: str,
    folder_id: str | None,
    context_project_ids: list[str],
    context_knowledge_base_ids: list[str],
    context_snippets: list[dict[str, str]],
    attached_document_ids: list[str],
    attached_file_ids: list[str],
    generated_file_ids: list[str] | None = None,
) -> dict[str, object]:
    context_document_ids = sorted(
        {snippet["document_id"] for snippet in context_snippets if snippet.get("document_id")}
    )
    return {
        "project_id": project_id,
        "folder_id": folder_id,
        "context_project_ids": context_project_ids,
        "context_document_ids": context_document_ids,
        "context_knowledge_base_ids": context_knowledge_base_ids,
        "context_snippet_count": len(context_snippets),
        "attached_document_ids": attached_document_ids,
        "attached_file_ids": attached_file_ids,
        "generated_file_ids": generated_file_ids or [],
    }


@router.post("/stream")
async def stream_chat(payload: ChatStreamRequest) -> StreamingResponse:
    store = get_store()
    general_project_id = _general_project_id(store)
    session = (
        store.get_chat_session(payload.session_id)
        if payload.session_id and hasattr(store, "get_chat_session")
        else None
    )
    agents = store.list_agents()
    primary_agent, target_agent, support_agents = select_orchestration_agents(
        agents=agents,
        selected_agent_id=payload.agent_id or (session.agent_id if session else None),
        requested_agent_ids=payload.agent_ids,
        multi_agent_mode=payload.multi_agent_mode,
    )
    projects = store.list_projects() if hasattr(store, "list_projects") else []
    projects_by_id = {project.id: project for project in projects}
    runtime_allowed_project_ids = _runtime_allowed_project_ids(
        [primary_agent, target_agent, *support_agents],
        general_project_id=general_project_id,
    )
    known_project_ids = {project.id for project in projects}
    requested_project_id = payload.project_id or (session.project_id if session else None)
    effective_project_id = requested_project_id or general_project_id
    if known_project_ids and effective_project_id not in known_project_ids:
        effective_project_id = general_project_id
    _validate_active_project_scope(
        active_project_id=effective_project_id,
        runtime_allowed_project_ids=runtime_allowed_project_ids,
    )
    if session is None:
        if settings.require_chat_title:
            _enforce_required_chat_title(payload)
        session = store.get_or_create_session(payload)
    session = _apply_stream_title_to_session(
        store,
        session,
        payload,
        require_title=settings.require_chat_title,
    )
    session = _promote_modeling_session(store, session, payload)
    effective_folder_id = payload.folder_id if payload.folder_id is not None else session.folder_id
    if (
        effective_project_id != session.project_id or effective_folder_id != session.folder_id
    ) and hasattr(store, "upsert_chat_session"):
        session = session.model_copy(
            update={
                "project_id": effective_project_id,
                "folder_id": effective_folder_id,
                "updated_at": now_utc(),
            }
        )
        store.upsert_chat_session(session)
    session = _clear_empty_draft_flag(store, session)
    normalized_context_project_ids = _normalize_project_ids(
        [effective_project_id],
        fallback_project_id=session.project_id or general_project_id,
        known_project_ids=known_project_ids,
    )
    effective_context_project_ids = [
        project_id
        for project_id in normalized_context_project_ids
        if project_id in runtime_allowed_project_ids
    ]
    if not effective_context_project_ids:
        effective_context_project_ids = (
            [general_project_id]
            if general_project_id in runtime_allowed_project_ids
            else list(runtime_allowed_project_ids)[:1]
        )
    effective_context_project_ids = effective_context_project_ids[:1]
    knowledge_bases = store.list_knowledge_bases() if hasattr(store, "list_knowledge_bases") else []
    knowledge_base_items = (
        store.list_knowledge_base_documents()
        if hasattr(store, "list_knowledge_base_documents")
        else []
    )
    effective_knowledge_base_ids = _knowledge_base_ids_for_runtime(
        project_id=effective_context_project_ids[0],
        projects_by_id=projects_by_id,
        primary_agent=primary_agent,
        target_agent=target_agent,
        support_agents=support_agents,
        payload_ids=payload.context_knowledge_base_ids,
        session_ids=session.context_knowledge_base_ids,
        knowledge_bases=knowledge_bases,
    )
    if payload.modeling_3d.enabled:
        return build_modeling_3d_stream_response(
            store,
            session,
            payload,
            effective_project_id=effective_project_id,
            effective_context_project_ids=effective_context_project_ids,
            effective_knowledge_base_ids=effective_knowledge_base_ids,
        )

    registry = ModelRegistry()
    model = registry.get_for_agent(primary_agent, fallback_model_id=session.model_id)
    if payload.response_mode == "image":
        if payload.image_model_id:
            selected_image_model = registry.get(payload.image_model_id)
            if ModelCapability.image_generation not in selected_image_model.capabilities:
                raise HTTPException(
                    status_code=400,
                    detail="O modelo selecionado não possui capacidade de geração de imagem.",
                )
            model = selected_image_model
        else:
            model = registry.get_image_model(model.provider)
            if ModelCapability.image_generation not in model.capabilities:
                raise HTTPException(
                    status_code=400,
                    detail="Nenhum modelo com capacidade de geração de imagem está disponível.",
                )
    elif payload.deep_research:
        model = registry.get_deep_research_model()
    if payload.reasoning_override == "long":
        model = model.model_copy(
            update={
                "reasoning_effort": "high",
                "max_output_tokens": max(model.max_output_tokens or 0, 4096),
            }
        )
    policy = store.get_cost_policy()
    tokens_in = estimate_tokens(payload.message)
    deep_research_pricing_required = payload.deep_research and not has_configured_pricing(model)
    image_generation_requested = payload.response_mode == "image"
    image_generation_pricing_required = image_generation_requested and not has_configured_pricing(
        model
    )
    reasoning_summary_requested = payload.reasoning_summary != "off"
    reasoning_summary_pricing_required = reasoning_summary_requested and not has_configured_pricing(
        model
    )
    reasoning_summary_provider_unsupported = (
        reasoning_summary_requested and model.provider != ProviderName.openai
    )
    estimated_tokens_out = (
        IMAGE_GENERATION_ESTIMATED_OUTPUT_TOKENS
        if image_generation_requested
        else 1150
        if reasoning_summary_requested
        else 900
    )
    current_spend_brl = monthly_spend(monthly_events_for_store(store))
    preflight = estimate_cost(
        model,
        policy,
        tokens_in=tokens_in,
        tokens_out=estimated_tokens_out,
        current_spend_brl=current_spend_brl,
    )
    preflight_cost_metadata = _cost_metadata(
        preflight_estimated_cost_brl=preflight.estimated_cost_brl,
        current_spend_brl=current_spend_brl,
        monthly_budget_brl=policy.monthly_budget_brl,
        warn_threshold_percent=policy.warn_threshold_percent,
        block_at_budget=policy.block_at_budget,
    )
    if (
        preflight.blocked
        or deep_research_pricing_required
        or image_generation_pricing_required
        or reasoning_summary_pricing_required
        or reasoning_summary_provider_unsupported
    ):
        if deep_research_pricing_required:
            block_reason = "deep_research_pricing_required"
            block_message = (
                "Deep Research bloqueado pelo Cost Governor: configure custo de input e output "
                "do modelo antes de usar pesquisa aprofundada."
            )
        elif image_generation_pricing_required:
            block_reason = "image_generation_pricing_required"
            block_message = (
                "Geração de imagem bloqueada pelo Cost Governor: configure custo de input "
                "e output do modelo de imagem antes de usar esse modo."
            )
        elif reasoning_summary_pricing_required:
            block_reason = "reasoning_summary_pricing_required"
            block_message = (
                "Resumo oficial de raciocínio bloqueado pelo Cost Governor: configure custo "
                "de input e output do modelo antes de ativar esse modo."
            )
        elif reasoning_summary_provider_unsupported:
            block_reason = "reasoning_summary_provider_unsupported"
            block_message = (
                "Resumo oficial de raciocínio está habilitado apenas para modelos OpenAI "
                "nesta versão."
            )
        else:
            block_reason = preflight.reason
            block_message = "Requisição bloqueada pelo Cost Governor."
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=payload.message,
            model_id=model.id,
        )
        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=block_message,
            model_id=model.id,
            metadata={
                "provider": "cost_governor",
                "persona": "JUDITE",
                "blocked": True,
                "reason": block_reason,
                "cost": preflight_cost_metadata,
            },
        )
        store.add_message(user_message)
        store.add_message(assistant_message)
        record_audit_event(
            AuditEvent(
                event_type="chat.blocked",
                provider=model.provider,
                model_id=model.id,
                tokens_in=tokens_in,
                tokens_out=0,
                estimated_cost_brl=preflight.estimated_cost_brl,
                metadata={
                    "session_id": session.id,
                    "reason": block_reason,
                    "provider": model.provider.value,
                    "provider_model_id": model.provider_model_id,
                    "model_display_name": model.display_name,
                    "preflight_tokens_out": estimated_tokens_out,
                    "cost": preflight_cost_metadata,
                    "deep_research": payload.deep_research,
                    "deep_research_max_tool_calls": payload.deep_research_max_tool_calls,
                    "reasoning_summary": payload.reasoning_summary,
                    "response_mode": payload.response_mode,
                    "image_model_id": payload.image_model_id,
                },
            )
        )
        return StreamingResponse(
            iter(
                [
                    _sse(
                        "meta",
                        {"session_id": session.id, "message_id": assistant_message.id},
                    ),
                    _runtime_status("blocked", "Bloqueado pelo Cost Governor", block_message),
                    _sse(
                        "error",
                        {
                            "reason": block_reason,
                            "message": block_message,
                            "estimated_cost_brl": preflight.estimated_cost_brl,
                        },
                    ),
                    _sse("done", {"session_id": session.id, "message_id": assistant_message.id}),
                ]
            ),
            media_type="text/event-stream",
            status_code=402,
        )

    attached_documents = []
    if payload.attached_document_ids:
        attached_document_ids = set(payload.attached_document_ids)
        attached_documents = [
            document for document in store.list_documents() if document.id in attached_document_ids
        ]
        found_document_ids = {document.id for document in attached_documents}
        missing_document_ids = sorted(attached_document_ids - found_document_ids)
        if missing_document_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Documentos anexados inválidos: "
                    + ", ".join(missing_document_ids[:5])
                    + ("..." if len(missing_document_ids) > 5 else "")
                ),
            )

    attached_files: list[PlatformFile] = []
    if payload.attached_file_ids and hasattr(store, "list_platform_files"):
        attached_file_ids = set(payload.attached_file_ids)
        attached_files = [
            platform_file
            for platform_file in store.list_platform_files()
            if platform_file.id in attached_file_ids
        ]
        found_file_ids = {platform_file.id for platform_file in attached_files}
        missing_file_ids = sorted(attached_file_ids - found_file_ids)
        if missing_file_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Arquivos anexados inválidos: "
                    + ", ".join(missing_file_ids[:5])
                    + ("..." if len(missing_file_ids) > 5 else "")
                ),
            )

    _validate_attachment_project_scope(
        active_project_id=effective_project_id,
        runtime_allowed_project_ids=runtime_allowed_project_ids,
        documents=attached_documents,
        files=attached_files,
    )

    user_metadata: dict[str, object] = {}
    if payload.attached_document_ids:
        user_metadata["attached_document_ids"] = payload.attached_document_ids
    if payload.attached_file_ids:
        user_metadata["attached_file_ids"] = payload.attached_file_ids
    if attached_files:
        user_metadata["attached_files"] = [
            {
                "id": platform_file.id,
                "file_id": platform_file.id,
                "filename": platform_file.filename,
                "original_filename": platform_file.original_filename,
                "content_type": platform_file.content_type,
                "size_bytes": platform_file.size_bytes,
                "url": (
                    f"{settings.public_base_url.rstrip('/')}/api/files/{platform_file.id}/content"
                ),
            }
            for platform_file in attached_files
        ]

    if attached_files and hasattr(store, "update_platform_file"):
        for platform_file in attached_files:
            metadata = (
                dict(platform_file.metadata) if isinstance(platform_file.metadata, dict) else {}
            )
            if not metadata.get("project_id"):
                metadata["project_id"] = effective_project_id
            if "folder_id" not in metadata:
                metadata["folder_id"] = effective_folder_id
            if not metadata.get("session_id"):
                metadata["session_id"] = session.id
            store.update_platform_file(
                platform_file.id,
                PlatformFileUpdate(metadata=metadata),
            )

    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=payload.message,
        model_id=model.id,
        metadata=user_metadata,
    )

    all_documents = store.list_documents() if hasattr(store, "list_documents") else []
    effective_knowledge_bases = [
        knowledge_base
        for knowledge_base in knowledge_bases
        if knowledge_base.id in effective_knowledge_base_ids and knowledge_base.enabled
    ]
    effective_knowledge_base_items = [
        item
        for item in knowledge_base_items
        if item.knowledge_base_id in effective_knowledge_base_ids and item.enabled
    ]
    project_folders = store.list_project_folders() if hasattr(store, "list_project_folders") else []
    mentioned_folder_ids = _mentioned_folder_ids(
        payload.message,
        projects_by_id=projects_by_id,
        project_folders=project_folders,
    )
    context_snippets = await _search_knowledge_base_context(
        message=payload.message,
        knowledge_bases=effective_knowledge_bases,
        knowledge_base_items=effective_knowledge_base_items,
        documents=all_documents,
        folder_ids=mentioned_folder_ids,
    )

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

    store.add_message(user_message)

    chat_history = []
    system_parts = []
    active_project = projects_by_id.get(effective_project_id)
    if active_project is not None:
        system_parts.append(
            f"Projeto dono desta conversa: {active_project.name} ({active_project.id})."
        )
    if effective_knowledge_bases:
        system_parts.append("Bases de conhecimento atreladas a esta execução:")
        for knowledge_base in effective_knowledge_bases:
            scope = f" Escopo: {knowledge_base.scope}" if knowledge_base.scope else ""
            system_parts.append(
                f"- {knowledge_base.name} ({knowledge_base.id}). "
                f"Descrição: {knowledge_base.description or 'sem descrição.'}{scope}"
            )
    if mentioned_folder_ids:
        mentioned_paths = [
            folder.path for folder in project_folders if folder.id in mentioned_folder_ids
        ]
        if mentioned_paths:
            system_parts.append(
                "Pastas citadas explicitamente pelo usuário: " + ", ".join(mentioned_paths) + "."
            )
    if context_snippets:
        system_parts.append(
            f"Contexto recuperado automaticamente da base vetorial (top {len(context_snippets)}):"
        )
        for snippet in context_snippets:
            system_parts.append(
                f"- {snippet['title']} / base {snippet['knowledge_base_name']} "
                f"[score {snippet['score']}]:\n{snippet['content']}"
            )
    if primary_agent is not None:
        system_parts.append(primary_agent.system_prompt)
        system_parts.append(
            f"Agente primário: {primary_agent.name}. "
            f"Modo de colaboração: {primary_agent.collaboration_mode}."
        )
        if primary_agent.role == "orchestrator":
            system_parts.append(
                "Este agente é o orquestrador obrigatório do fluxo. Toda solicitação deve "
                "passar por ele primeiro para roteamento, políticas, custo, privacidade, "
                "delegação e síntese final."
            )
    if target_agent is not None:
        system_parts.append(
            f"Agente solicitado pelo usuário: {target_agent.name} ({target_agent.role}). "
            "Avalie se deve delegar a ele, incorporar sua especialidade ou responder diretamente."
        )
    if payload.reasoning_override == "long":
        system_parts.append(
            "Raciocínio longo ativado somente para esta conversa. "
            "Estruture a análise com mais cuidado antes da resposta final."
        )
    if payload.deep_research:
        system_parts.append(
            "Pesquisa aprofundada solicitada. Use fontes externas, destaque evidências, "
            "inclua citações clicáveis quando disponíveis e diferencie fatos de inferências."
        )
    if payload.reasoning_summary != "off":
        system_parts.append(
            "Resumo oficial de raciocínio solicitado. Não exponha cadeia de pensamento bruta; "
            "use somente o resumo autorizado pelo provedor quando ele estiver disponível."
        )
    if payload.response_mode == "image":
        system_parts.append(
            "Modo imagem ativado. Use a mensagem do usuário como briefing visual principal."
        )
    if support_agents:
        system_parts.append("Agentes de apoio disponíveis nesta conversa:")
        for agent in support_agents:
            system_parts.append(
                f"- {agent.name} ({agent.role}, modo {agent.collaboration_mode}): "
                f"{agent.description}\n"
                f"Prompt operacional: {agent.system_prompt}"
            )
    if attached_documents:
        system_parts.append("Arquivos/contextos anexados a esta conversa:")
        for document in attached_documents:
            preview = ""
            if document.storage_path:
                preview = read_text_preview(document.storage_path, settings.files_dir)
            tags = ", ".join(document.tags) or "sem tags"
            system_parts.append(
                f"- {document.title} ({document.source_type}, tags: {tags})\n{preview}"
            )
    if attached_files:
        system_parts.append("Arquivos anexados a esta conversa:")
        for platform_file in attached_files:
            preview = read_text_preview(platform_file.storage_path, settings.data_dir)
            tags = ", ".join(platform_file.tags) or "sem tags"
            file_type = platform_file.content_type or "arquivo"
            system_parts.append(
                f"- {platform_file.original_filename} ({file_type}, tags: {tags})\n"
                f"{preview or '[arquivo não textual ou prévia indisponível]'}"
            )
    if system_parts:
        chat_history.append({"role": "system", "content": "\n\n".join(system_parts)})

    if hasattr(store, "get_chat_session"):
        target_session = store.get_chat_session(session.id)
    else:
        target_session = next(
            (
                chat_session
                for chat_session in store.list_chat_sessions()
                if chat_session.id == session.id
            ),
            None,
        )
    if target_session is not None:
        chat_history.extend(
            [
                {"role": message.role, "content": message.content}
                for message in target_session.messages
                if message.role in {"system", "user", "assistant"}
            ]
        )
    if not chat_history or chat_history[-1]["content"] != payload.message:
        chat_history.append({"role": "user", "content": payload.message})

    gateway = LLMGateway()
    fallback_reason: str | None = None

    async def remote_tokens() -> AsyncIterator[ProviderStreamEvent]:
        nonlocal fallback_reason
        try:
            if payload.response_mode == "image":
                yield token_event(await gateway.generate_image(model, payload.message))
                return
            if payload.deep_research:
                async for token in gateway.deep_research(
                    model,
                    chat_history,
                    payload.deep_research_max_tool_calls,
                ):
                    yield token_event(token)
                return
            async for event in gateway.stream_chat(model, chat_history, payload.reasoning_summary):
                yield event
        except ProviderConfigurationError as exc:
            fallback_reason = str(exc)
            if not settings.allow_dev_llm:
                raise
            for token in judite_dev_response(payload.message, model.id).split(" "):
                yield token_event(token + " ")

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="",
        model_id=model.id,
        metadata={"provider": model.provider.value, "persona": "JUDITE"},
    )
    if primary_agent is not None:
        assistant_message.metadata["agent_id"] = primary_agent.id
        assistant_message.metadata["agent_name"] = primary_agent.name
    if target_agent is not None:
        assistant_message.metadata["target_agent_id"] = target_agent.id
        assistant_message.metadata["target_agent_name"] = target_agent.name
    if support_agents:
        assistant_message.metadata["support_agent_ids"] = [agent.id for agent in support_agents]

    async def events() -> AsyncIterator[str]:
        yield _sse("meta", {"session_id": session.id, "message_id": assistant_message.id})
        yield _runtime_status(
            "context", "Preparando contexto", "Montando persona, histórico e anexos."
        )
        if payload.attached_document_ids:
            yield _runtime_status(
                "context_files", "Lendo anexos", "Aplicando contexto local permitido."
            )
        if payload.multi_agent_mode:
            yield _runtime_status(
                "multi_agent",
                "Coordenando agentes",
                "Preparando agentes selecionados para colaborar.",
            )
        if payload.reasoning_override == "long":
            yield _runtime_status(
                "reasoning",
                "Raciocínio longo",
                "Aumentando orçamento e cuidado antes da resposta.",
            )
        if payload.deep_research:
            yield _runtime_status(
                "deep_research",
                "Pesquisa aprofundada",
                f"Limite: {payload.deep_research_max_tool_calls} chamadas de ferramenta.",
            )
        elif payload.response_mode == "image":
            yield _runtime_status(
                "image", "Gerando imagem", "Enviando briefing visual ao provedor."
            )
        else:
            yield _runtime_status("thinking", "JUDITE pensando", "Preparando a resposta do modelo.")
        if payload.reasoning_summary != "off":
            yield _runtime_status(
                "reasoning_summary",
                "Resumo oficial ativado",
                "Pode aumentar tokens de saída; exibirei somente o resumo autorizado.",
            )
        output_parts: list[str] = []
        reasoning_summary_parts: list[str] = []
        provider_error: str | None = None
        first_token = True
        try:
            async for stream_event in remote_tokens():
                if stream_event.kind == "reasoning_summary":
                    reasoning_summary_parts.append(stream_event.content)
                    yield _sse("reasoning_summary", {"content": stream_event.content})
                    continue
                if first_token:
                    first_token = False
                    yield _runtime_status(
                        "answering", "Respondendo", "A resposta começou a chegar."
                    )
                output_parts.append(stream_event.content)
                yield _sse("token", {"content": stream_event.content})
        except (ProviderConfigurationError, ProviderExecutionError) as exc:
            provider_error = str(exc)
            error_message = f"Não consegui concluir a chamada ao provedor: {provider_error}"
            output_parts.append(error_message)
            yield _sse("error", {"message": error_message, "reason": provider_error})
        assistant_message.content = "".join(output_parts)
        generated_files: list[PlatformFile] = []
        if payload.response_mode == "image":
            assistant_message.content, generated_files = await save_generated_images_from_markdown(
                assistant_message.content,
                store,
                session_id=session.id,
                message_id=assistant_message.id,
                project_id=effective_project_id,
                folder_id=effective_folder_id,
            )
        if generated_files:
            assistant_message.metadata["generated_file_ids"] = [file.id for file in generated_files]
        if fallback_reason:
            assistant_message.metadata["fallback_reason"] = fallback_reason
            assistant_message.metadata["provider"] = "dev"
        if reasoning_summary_parts:
            assistant_message.metadata["reasoning_summary"] = "".join(reasoning_summary_parts)
        if provider_error:
            assistant_message.metadata["provider_error"] = provider_error
        store.add_message(assistant_message)
        billable_output_text = assistant_message.content + "".join(reasoning_summary_parts)
        tokens_out = estimate_tokens(billable_output_text)
        if payload.response_mode == "image" and not provider_error:
            tokens_out = max(tokens_out, IMAGE_GENERATION_ESTIMATED_OUTPUT_TOKENS)
        final_cost = estimate_cost(
            model,
            policy,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            current_spend_brl=current_spend_brl,
        )
        final_cost_metadata = _cost_metadata(
            preflight_estimated_cost_brl=preflight.estimated_cost_brl,
            final_estimated_cost_brl=final_cost.estimated_cost_brl,
            current_spend_brl=current_spend_brl,
            monthly_budget_brl=policy.monthly_budget_brl,
            warn_threshold_percent=policy.warn_threshold_percent,
            block_at_budget=policy.block_at_budget,
        )
        generated_file_ids = assistant_message.metadata.get("generated_file_ids", [])
        record_audit_event(
            AuditEvent(
                event_type="chat.stream",
                provider=model.provider,
                model_id=model.id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                estimated_cost_brl=final_cost.estimated_cost_brl,
                metadata={
                    "session_id": session.id,
                    "provider": assistant_message.metadata.get("provider"),
                    "provider_model_id": model.provider_model_id,
                    "model_display_name": model.display_name,
                    "preflight_tokens_out": estimated_tokens_out,
                    "cost": final_cost_metadata,
                    "agent_id": assistant_message.metadata.get("agent_id"),
                    "target_agent_id": assistant_message.metadata.get("target_agent_id"),
                    "support_agent_ids": assistant_message.metadata.get("support_agent_ids", []),
                    "reasoning_override": payload.reasoning_override,
                    "deep_research": payload.deep_research,
                    "deep_research_max_tool_calls": payload.deep_research_max_tool_calls,
                    "response_mode": payload.response_mode,
                    "reasoning_summary": payload.reasoning_summary,
                    "multi_agent_mode": payload.multi_agent_mode,
                    **_context_audit_metadata(
                        project_id=effective_project_id,
                        folder_id=effective_folder_id,
                        context_project_ids=effective_context_project_ids,
                        context_knowledge_base_ids=effective_knowledge_base_ids,
                        context_snippets=context_snippets,
                        attached_document_ids=payload.attached_document_ids,
                        attached_file_ids=payload.attached_file_ids,
                        generated_file_ids=generated_file_ids
                        if isinstance(generated_file_ids, list)
                        else [],
                    ),
                    "fallback_reason": fallback_reason,
                    "provider_error": provider_error,
                },
            )
        )
        yield _sse("done", {"session_id": session.id, "message_id": assistant_message.id})

    return StreamingResponse(events(), media_type="text/event-stream")
