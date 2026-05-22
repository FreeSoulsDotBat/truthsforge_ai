from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.audit.service import record_audit_event
from app.chat.session_cleanup import (
    delete_chat_session_with_files,
    session_related_file_ids,
)
from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    MAX_CONTEXT_KNOWLEDGE_BASE_IDS,
    Agent,
    AuditEvent,
    ChatAttachmentAnalyzeRequest,
    ChatAttachmentAnalyzeResponse,
    ChatMessage,
    ChatModelingStage,
    ChatSession,
    ChatSessionContextUpdate,
    ChatSessionCreate,
    ChatSessionDeleteResult,
    ChatSessionMoveRequest,
    ChatSessionWithMessages,
    ChatStreamRequest,
    Document,
    KnowledgeBase,
    KnowledgeBaseDocument,
    ModelCapability,
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanStatus,
    PlatformFile,
    PlatformFileCreate,
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
from app.files.library import counted_filename, find_duplicate
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
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.service import get_modeling_service
from app.rag.embeddings import embed_text
from app.rag.indexing import ensure_document_for_platform_file
from app.rag.vector_store import QdrantVectorStore
from app.storage.store import get_store
from app.workers.index_queue import enqueue_platform_file_index

router = APIRouter()
DATA_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(data:(image/[-+.\w]+);base64,([A-Za-z0-9+/=\s]+)\)")
REMOTE_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
DOCUMENT_COLLECTION = "truths_forge_documents"
IMAGE_EXTENSIONS = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
DEFAULT_CHAT_TITLES = {"novo chat", "new chat"}
MAX_CONTEXT_PROJECTS = 3
MAX_CONTEXT_DOCUMENTS = 20
FOLDER_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_./-]+)")
GENERATED_IMAGE_MAX_BYTES = 50 * 1024 * 1024
IMAGE_GENERATION_ESTIMATED_OUTPUT_TOKENS = 1290
USD_TO_BRL = 5.0


def _create_generated_image_file(
    *,
    raw: bytes,
    content_type: str,
    store,
    session_id: str,
    message_id: str,
    project_id: str,
    folder_id: str | None,
    index: int,
    existing_files: list[PlatformFile],
    existing_names: set[str],
    source_url: str | None = None,
) -> PlatformFile:
    normalized_content_type = content_type.split(";")[0].strip().lower() or "image/png"
    checksum = hashlib.sha256(raw).hexdigest()
    extension = IMAGE_EXTENSIONS.get(normalized_content_type, ".png")
    filename = counted_filename(
        f"imagem-gerada-{message_id[:8]}-{index}{extension}", existing_names
    )
    existing_names.add(filename)
    target_dir = settings.files_dir / "generated" / session_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(raw)

    duplicate = find_duplicate(
        existing_files,
        filename=filename,
        size_bytes=len(raw),
        checksum_sha256=checksum,
    )
    metadata: dict[str, Any] = {
        "session_id": session_id,
        "project_id": project_id,
        "folder_id": folder_id,
        "message_id": message_id,
        "generated_from": "chat.image",
    }
    if source_url:
        metadata["source_url"] = source_url

    platform_file = store.create_platform_file(
        PlatformFileCreate(
            filename=filename,
            original_filename=filename,
            content_type=normalized_content_type,
            size_bytes=len(raw),
            storage_path=str(target_path),
            checksum_sha256=checksum,
            duplicate_of_id=duplicate.id if duplicate else None,
            source="generated",
            tags=["generated", "image"],
            metadata=metadata,
        )
    )
    ensure_document_for_platform_file(
        store,
        platform_file,
        project_id=project_id,
        folder_id=folder_id,
        tags=["generated", "image"],
        metadata={
            "session_id": session_id,
            "message_id": message_id,
            "generated_from": "chat.image",
        },
        force_status_pending=True,
    )
    enqueue_platform_file_index(platform_file.id)
    existing_files.append(platform_file)
    return platform_file


async def _download_remote_generated_image(url: str) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if not content_type.startswith("image/"):
                    return None

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > GENERATED_IMAGE_MAX_BYTES:
                        return None
                    chunks.append(chunk)
    except httpx.HTTPError:
        return None
    return b"".join(chunks), content_type


async def save_generated_images_from_markdown(
    content: str,
    store,
    *,
    session_id: str,
    message_id: str,
    project_id: str,
    folder_id: str | None,
) -> tuple[str, list[PlatformFile]]:
    data_matches = list(DATA_IMAGE_PATTERN.finditer(content))
    remote_matches = list(REMOTE_IMAGE_PATTERN.finditer(content))
    if not data_matches and not remote_matches:
        return content, []

    settings.ensure_local_dirs()
    generated_files: list[PlatformFile] = []
    existing_files = store.list_platform_files()
    existing_names = {
        platform_file.filename for platform_file in existing_files if platform_file.filename
    }
    updated_content = content

    for match in data_matches:
        content_type = match.group(1)
        try:
            raw = base64.b64decode(match.group(2), validate=False)
        except ValueError:
            continue
        platform_file = _create_generated_image_file(
            raw=raw,
            content_type=content_type,
            store=store,
            session_id=session_id,
            message_id=message_id,
            project_id=project_id,
            folder_id=folder_id,
            index=len(generated_files) + 1,
            existing_files=existing_files,
            existing_names=existing_names,
        )
        generated_files.append(platform_file)
        stored_url = f"{settings.public_base_url.rstrip('/')}/api/files/{platform_file.id}/content"
        updated_content = updated_content.replace(
            match.group(0), f"![Imagem gerada]({stored_url})", 1
        )

    local_file_prefix = f"{settings.public_base_url.rstrip('/')}/api/files/"
    for match in remote_matches:
        source_url = match.group(1)
        if source_url.startswith(local_file_prefix):
            continue
        downloaded = await _download_remote_generated_image(source_url)
        if downloaded is None:
            continue
        raw, content_type = downloaded
        platform_file = _create_generated_image_file(
            raw=raw,
            content_type=content_type,
            store=store,
            session_id=session_id,
            message_id=message_id,
            project_id=project_id,
            folder_id=folder_id,
            index=len(generated_files) + 1,
            existing_files=existing_files,
            existing_names=existing_names,
            source_url=source_url,
        )
        generated_files.append(platform_file)
        stored_url = f"{settings.public_base_url.rstrip('/')}/api/files/{platform_file.id}/content"
        updated_content = updated_content.replace(
            match.group(0), f"![Imagem gerada]({stored_url})", 1
        )

    return updated_content, generated_files


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


def _sync_modeling_plan_session(store, session: ChatSession, plan: ModelingPlan) -> ChatSession:
    updated = session.model_copy(
        update={
            "is_modeling_3d": True,
            "modeling_software_preference": plan.software_choice,
            "modeling_stage": ChatModelingStage.editing,
            "modeling_plan_id": plan.id,
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "upsert_chat_session"):
        store.upsert_chat_session(updated)
    return updated


def _sync_modeling_plan_proposed(store, session: ChatSession, plan: ModelingPlan) -> ChatSession:
    """Link a freshly proposed (not yet executed) plan to the chat and move it
    to ``planning``.

    Mirrors :func:`_sync_modeling_plan_session` but stops at ``planning``
    instead of ``editing``: the plan is awaiting the user's decision on the
    ModelingPlanCard. Execution only happens after an explicit approval
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


def _general_project_id(store) -> str:
    if hasattr(store, "list_projects"):
        general = next((project for project in store.list_projects() if project.is_general), None)
        if general is not None:
            return general.id
    return DEFAULT_GENERAL_PROJECT_ID


def _normalize_project_ids(
    project_ids: list[str], *, fallback_project_id: str, known_project_ids: set[str]
) -> list[str]:
    normalized: list[str] = []
    for raw_id in project_ids:
        if raw_id not in known_project_ids:
            continue
        if raw_id in normalized:
            continue
        normalized.append(raw_id)
    if not normalized:
        return [fallback_project_id]
    return normalized[:MAX_CONTEXT_PROJECTS]


def _agent_allowed_project_ids(agent: Agent | None, *, general_project_id: str) -> set[str]:
    if agent is None:
        return {general_project_id}
    allowed = set(agent.allowed_project_ids or [])
    if not allowed:
        return {general_project_id}
    return allowed


def _runtime_allowed_project_ids(
    agents: list[Agent | None], *, general_project_id: str
) -> set[str]:
    allowed: set[str] = set()
    for agent in agents:
        allowed.update(_agent_allowed_project_ids(agent, general_project_id=general_project_id))
    return allowed or {general_project_id}


def _validate_active_project_scope(
    *, active_project_id: str, runtime_allowed_project_ids: set[str]
) -> None:
    if active_project_id in runtime_allowed_project_ids:
        return
    raise HTTPException(
        status_code=403,
        detail="O agente selecionado não tem acesso ao projeto ativo desta conversa.",
    )


def _metadata_project_id(metadata: dict[str, Any] | None) -> str:
    if isinstance(metadata, dict):
        raw_project_id = metadata.get("project_id")
        if isinstance(raw_project_id, str) and raw_project_id.strip():
            return raw_project_id
    return DEFAULT_GENERAL_PROJECT_ID


def _document_scope_project_id(document: Document) -> str:
    return document.project_id or _metadata_project_id(document.metadata)


def _platform_file_scope_project_id(platform_file: PlatformFile) -> str:
    return _metadata_project_id(platform_file.metadata)


def _format_scoped_attachment_error(ids: list[str]) -> str:
    return ", ".join(ids[:5]) + ("..." if len(ids) > 5 else "")


def _validate_attachment_project_scope(
    *,
    active_project_id: str,
    runtime_allowed_project_ids: set[str],
    documents: list[Document],
    files: list[PlatformFile],
) -> None:
    if documents or files:
        if active_project_id not in runtime_allowed_project_ids:
            raise HTTPException(
                status_code=403,
                detail="O agente selecionado não tem acesso ao projeto ativo dos anexos.",
            )

    invalid_document_ids = [
        document.id
        for document in documents
        if _document_scope_project_id(document) != active_project_id
    ]
    if invalid_document_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "Documentos anexados fora do escopo do projeto ativo: "
                + _format_scoped_attachment_error(invalid_document_ids)
            ),
        )

    invalid_file_ids = [
        platform_file.id
        for platform_file in files
        if _platform_file_scope_project_id(platform_file) != active_project_id
    ]
    if invalid_file_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "Arquivos anexados fora do escopo do projeto ativo: "
                + _format_scoped_attachment_error(invalid_file_ids)
            ),
        )


def _folder_lookup_key(project_name: str, folder_path: str) -> str:
    normalized_project = project_name.strip().replace(" ", "_")
    normalized_path = folder_path.strip().replace(" ", "_")
    return f"{normalized_project}/{normalized_path}".strip("/").lower()


def _mentioned_folder_ids(
    message: str,
    *,
    projects_by_id: dict[str, Any],
    project_folders: list[Any],
) -> set[str]:
    mentions = {
        match.group(1).strip().replace("\\", "/").replace(" ", "_").lower()
        for match in FOLDER_MENTION_PATTERN.finditer(message)
        if match.group(1).strip()
    }
    if not mentions:
        return set()

    folder_id_by_key: dict[str, str] = {}
    for folder in project_folders:
        project = projects_by_id.get(folder.project_id)
        if project is None:
            continue
        key = _folder_lookup_key(project.name, folder.path)
        folder_id_by_key[key] = folder.id
    return {folder_id for key, folder_id in folder_id_by_key.items() if key in mentions}


def _indexed_documents_for_projects(
    documents: list[Document], project_ids: set[str]
) -> list[Document]:
    return [
        document
        for document in documents
        if document.indexed
        and str(document.index_status) == "completed"
        and document.project_id in project_ids
    ]


def _select_context_documents(
    *,
    documents: list[Document],
    selected_document_ids: list[str],
) -> list[Document]:
    if not selected_document_ids:
        return []
    allowed = set(selected_document_ids[:MAX_CONTEXT_DOCUMENTS])
    selected = [document for document in documents if document.id in allowed]
    selected.sort(key=lambda document: selected_document_ids.index(document.id))
    return selected[:MAX_CONTEXT_DOCUMENTS]


def _normalize_knowledge_base_ids(
    knowledge_base_ids: list[str],
    *,
    knowledge_bases: list[KnowledgeBase],
) -> list[str]:
    known_ids = {knowledge_base.id for knowledge_base in knowledge_bases if knowledge_base.enabled}
    normalized: list[str] = []
    for raw_id in knowledge_base_ids:
        if raw_id not in known_ids or raw_id in normalized:
            continue
        normalized.append(raw_id)
    return normalized[:MAX_CONTEXT_KNOWLEDGE_BASE_IDS]


def _allowed_knowledge_base_ids_for_runtime(
    *,
    project_id: str,
    projects_by_id: dict[str, Any],
    primary_agent: Agent | None,
    target_agent: Agent | None,
    support_agents: list[Agent],
    knowledge_bases: list[KnowledgeBase],
) -> list[str]:
    ordered: list[str] = []
    project = projects_by_id.get(project_id)
    if project is not None:
        ordered.extend(getattr(project.context, "knowledge_base_ids", []) or [])
    for agent in [primary_agent, target_agent, *support_agents]:
        if agent is None:
            continue
        ordered.extend(agent.knowledge_base_ids or [])
    return _normalize_knowledge_base_ids(ordered, knowledge_bases=knowledge_bases)


def _knowledge_base_ids_for_runtime(
    *,
    project_id: str,
    projects_by_id: dict[str, Any],
    primary_agent: Agent | None,
    target_agent: Agent | None,
    support_agents: list[Agent],
    payload_ids: list[str],
    session_ids: list[str],
    knowledge_bases: list[KnowledgeBase],
) -> list[str]:
    allowed_ids = _allowed_knowledge_base_ids_for_runtime(
        project_id=project_id,
        projects_by_id=projects_by_id,
        primary_agent=primary_agent,
        target_agent=target_agent,
        support_agents=support_agents,
        knowledge_bases=knowledge_bases,
    )
    allowed_set = set(allowed_ids)
    if payload_ids:
        return [
            knowledge_base_id
            for knowledge_base_id in _normalize_knowledge_base_ids(
                payload_ids, knowledge_bases=knowledge_bases
            )
            if knowledge_base_id in allowed_set
        ][:MAX_CONTEXT_KNOWLEDGE_BASE_IDS]
    if session_ids:
        return [
            knowledge_base_id
            for knowledge_base_id in _normalize_knowledge_base_ids(
                session_ids, knowledge_bases=knowledge_bases
            )
            if knowledge_base_id in allowed_set
        ][:MAX_CONTEXT_KNOWLEDGE_BASE_IDS]

    return allowed_ids


def _knowledge_base_document_index(
    items: list[KnowledgeBaseDocument], knowledge_base_ids: set[str]
) -> dict[str, list[KnowledgeBaseDocument]]:
    indexed: dict[str, list[KnowledgeBaseDocument]] = {}
    for item in items:
        if not item.enabled or item.knowledge_base_id not in knowledge_base_ids:
            continue
        indexed.setdefault(item.document_id, []).append(item)
    return indexed


# Auto-titulação via OpenAI removida em Onda 2.10 (ADR-014). Todo chat
# precisa carregar um título não-vazio antes da primeira mensagem
# (validado em ChatSessionCreate + Onda 2.9 no stream handler).


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


def _project_scope_matches(
    raw_project_id: str | None,
    *,
    active_project_id: str | None,
    scope_mode: str,
) -> bool:
    normalized = raw_project_id or None
    global_ids = {None, DEFAULT_GENERAL_PROJECT_ID}
    if scope_mode == "global_only":
        return normalized in global_ids
    if scope_mode == "project_only":
        if active_project_id:
            return normalized == active_project_id
        return normalized in global_ids
    if scope_mode == "project_plus_global":
        if active_project_id:
            return normalized in {active_project_id, None, DEFAULT_GENERAL_PROJECT_ID}
        return normalized in global_ids
    return True


async def _search_project_context(
    *,
    message: str,
    project_ids: set[str],
    selected_document_ids: set[str],
    max_documents: int,
    folder_ids: set[str],
) -> list[dict[str, str]]:
    if not message.strip():
        return []
    vector_store = QdrantVectorStore()
    try:
        results = await vector_store.search(
            DOCUMENT_COLLECTION,
            embed_text(message),
            max(8, min(80, max_documents * 4)),
        )
    except Exception:
        return []

    snippets: list[dict[str, str]] = []
    for item in results:
        raw_payload = item.get("payload") or {}
        raw_project_id = str(raw_payload.get("project_id") or "")
        if project_ids and raw_project_id not in project_ids:
            continue
        raw_folder_id = raw_payload.get("folder_id")
        if folder_ids and str(raw_folder_id or "") not in folder_ids:
            continue
        raw_document_id = str(raw_payload.get("document_id") or "")
        if selected_document_ids and raw_document_id not in selected_document_ids:
            continue
        content = str(raw_payload.get("content") or "").strip()
        if not content:
            continue
        snippets.append(
            {
                "title": str(raw_payload.get("title") or "Documento"),
                "content": content,
                "project_id": str(raw_payload.get("project_id") or ""),
                "folder_id": str(raw_folder_id or ""),
                "score": f"{float(item.get('score', 0)):.3f}",
            }
        )
        if len(snippets) >= max_documents:
            break
    return snippets


async def _search_knowledge_base_context(
    *,
    message: str,
    knowledge_bases: list[KnowledgeBase],
    knowledge_base_items: list[KnowledgeBaseDocument],
    documents: list[Document],
    folder_ids: set[str],
) -> list[dict[str, str]]:
    if not message.strip() or not knowledge_bases:
        return []

    active_bases = [knowledge_base for knowledge_base in knowledge_bases if knowledge_base.enabled]
    active_base_ids = {knowledge_base.id for knowledge_base in active_bases}
    items_by_document_id = _knowledge_base_document_index(knowledge_base_items, active_base_ids)
    if not items_by_document_id:
        return []

    document_by_id = {
        document.id: document
        for document in documents
        if document.indexed and str(document.index_status) == "completed"
    }
    active_bases_by_id = {knowledge_base.id: knowledge_base for knowledge_base in active_bases}
    base_document_hits: dict[str, set[str]] = {
        knowledge_base.id: set() for knowledge_base in active_bases
    }
    document_chunk_hits: dict[tuple[str, str], int] = {}
    max_documents_total = min(
        MAX_CONTEXT_DOCUMENTS,
        sum(knowledge_base.max_documents_per_query for knowledge_base in active_bases),
    )
    vector_limit = max(8, min(120, max_documents_total * 5))

    vector_store = QdrantVectorStore()
    try:
        results = await vector_store.search(DOCUMENT_COLLECTION, embed_text(message), vector_limit)
    except Exception:
        return []

    ranked: list[tuple[float, dict[str, str]]] = []
    for item in results:
        raw_payload = item.get("payload") or {}
        raw_document_id = str(raw_payload.get("document_id") or "")
        document = document_by_id.get(raw_document_id)
        if document is None:
            continue
        if folder_ids and str(raw_payload.get("folder_id") or "") not in folder_ids:
            continue
        memberships = items_by_document_id.get(raw_document_id, [])
        if not memberships:
            continue

        selected_membership: KnowledgeBaseDocument | None = None
        selected_base: KnowledgeBase | None = None
        for membership in sorted(memberships, key=lambda value: value.priority, reverse=True):
            candidate_base = active_bases_by_id.get(membership.knowledge_base_id)
            if candidate_base is None:
                continue
            base_documents = base_document_hits[candidate_base.id]
            document_already_counted = document.id in base_documents
            if (
                not document_already_counted
                and len(base_documents) >= candidate_base.max_documents_per_query
            ):
                continue
            chunk_key = (candidate_base.id, document.id)
            if document_chunk_hits.get(chunk_key, 0) >= candidate_base.max_chunks_per_document:
                continue
            selected_membership = membership
            selected_base = candidate_base
            break
        if selected_membership is None or selected_base is None:
            continue

        content = str(raw_payload.get("content") or "").strip()
        if not content:
            continue
        base_document_hits[selected_base.id].add(document.id)
        chunk_key = (selected_base.id, document.id)
        document_chunk_hits[chunk_key] = document_chunk_hits.get(chunk_key, 0) + 1
        vector_score = float(item.get("score", 0))
        priority_boost = selected_membership.priority * 0.015
        pinned_boost = 0.03 if document.pinned else 0
        score = vector_score + priority_boost + pinned_boost
        ranked.append(
            (
                score,
                {
                    "title": str(raw_payload.get("title") or document.title or "Documento"),
                    "content": content,
                    "knowledge_base_id": selected_base.id,
                    "knowledge_base_name": selected_base.name,
                    "document_id": document.id,
                    "folder_id": str(raw_payload.get("folder_id") or ""),
                    "score": f"{score:.3f}",
                    "vector_score": f"{vector_score:.3f}",
                },
            )
        )
        if len(ranked) >= MAX_CONTEXT_DOCUMENTS:
            break

    ranked.sort(key=lambda value: value[0], reverse=True)
    return [item for _score, item in ranked[:MAX_CONTEXT_DOCUMENTS]]


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


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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


def _runtime_status(stage: str, label: str, detail: str | None = None) -> str:
    payload = {"stage": stage, "label": label}
    if detail:
        payload["detail"] = detail
    return _sse("status", payload)


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

    for chat_session in store.list_chat_sessions():
        if chat_session.id == session.id:
            chat_history.extend(
                [
                    {"role": message.role, "content": message.content}
                    for message in chat_session.messages
                    if message.role in {"system", "user", "assistant"}
                ]
            )
            break
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
