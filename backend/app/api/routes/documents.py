import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    Document,
    DocumentBatchRequest,
    DocumentCreate,
    DocumentFromFileCreate,
    DocumentPage,
    DocumentSearchRequest,
    DocumentSearchResult,
    DocumentTextCreate,
    JobStatus,
    KnowledgeCategory,
    KnowledgeCategoryCreate,
    KnowledgeCategoryUpdate,
    now_utc,
)
from app.files.processor import extension_for_source_type
from app.rag.embeddings import embed_text
from app.rag.indexing import ensure_document_for_platform_file, index_document_content
from app.rag.vector_store import QdrantVectorStore
from app.storage.store import get_store
from app.workers.index_queue import enqueue_platform_file_index

router = APIRouter()
DOCUMENT_COLLECTION = "truths_forge_documents"


def _query_terms(query: str) -> set[str]:
    return {term for term in re.findall(r"[\wÀ-ÿ]{2,}", query.lower()) if term}


def _keyword_score(query: str, *values: str) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    haystack = " ".join(values).lower()
    matches = sum(1 for term in terms if term in haystack)
    return matches / len(terms)


def _match_condition(key: str, values: list[str]) -> dict[str, object] | None:
    normalized = [value for value in dict.fromkeys(values) if value]
    if not normalized:
        return None
    if len(normalized) == 1:
        return {"key": key, "match": {"value": normalized[0]}}
    return {"key": key, "match": {"any": normalized}}


def _vector_payload_filter(
    *,
    document_ids: set[str] | None,
    folder_ids: list[str],
    category_ids: list[str],
    tags: list[str],
    source_types: list[str],
) -> dict[str, object] | None:
    must: list[dict[str, object]] = []
    for condition in [
        _match_condition("document_id", sorted(document_ids) if document_ids is not None else []),
        _match_condition("folder_id", folder_ids),
        _match_condition("category_id", category_ids),
        _match_condition("tags", tags),
        _match_condition("source_type", source_types),
    ]:
        if condition is not None:
            must.append(condition)
    return {"must": must} if must else None


def _matches_document_filters(
    document: Document,
    *,
    query: str | None,
    project_id: str | None,
    folder_id: str | None,
    source_type: str | None,
    indexed: bool | None,
) -> bool:
    if project_id and document.project_id != project_id:
        return False
    if folder_id and document.folder_id != folder_id:
        return False
    if source_type and document.source_type != source_type:
        return False
    if indexed is not None and bool(document.indexed) != bool(indexed):
        return False
    if query:
        normalized_query = query.strip().lower()
        if normalized_query:
            haystack = " ".join(
                [
                    document.title.lower(),
                    document.source_type.lower(),
                    " ".join(tag.lower() for tag in document.tags),
                ]
            )
            if normalized_query not in haystack:
                return False
    return True


@router.get("", response_model=list[Document])
def list_documents(
    query: str | None = None,
    project_id: str | None = None,
    folder_id: str | None = None,
    source_type: str | None = None,
    indexed: bool | None = None,
) -> list[Document]:
    documents = get_store().list_documents()
    filtered = [
        document
        for document in documents
        if _matches_document_filters(
            document,
            query=query,
            project_id=project_id,
            folder_id=folder_id,
            source_type=source_type,
            indexed=indexed,
        )
    ]
    return sorted(filtered, key=lambda item: item.updated_at, reverse=True)


@router.get("/page", response_model=DocumentPage)
def list_documents_page(
    limit: int = 50,
    offset: int = 0,
    query: str | None = None,
    project_id: str | None = None,
    folder_id: str | None = None,
    source_type: str | None = None,
    indexed: bool | None = None,
) -> DocumentPage:
    normalized_limit = max(1, min(int(limit), 200))
    normalized_offset = max(0, int(offset))
    filtered = list_documents(
        query=query,
        project_id=project_id,
        folder_id=folder_id,
        source_type=source_type,
        indexed=indexed,
    )
    total = len(filtered)
    items = filtered[normalized_offset : normalized_offset + normalized_limit]
    return DocumentPage(
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
        has_more=(normalized_offset + len(items)) < total,
    )


@router.post("/batch", response_model=list[Document])
def list_documents_by_ids(payload: DocumentBatchRequest) -> list[Document]:
    requested_ids = list(dict.fromkeys(item for item in payload.ids if item.strip()))
    if not requested_ids:
        return []
    documents_by_id = {document.id: document for document in get_store().list_documents()}
    return [
        documents_by_id[document_id]
        for document_id in requested_ids
        if document_id in documents_by_id
    ]


@router.get("/categories", response_model=list[KnowledgeCategory])
def list_knowledge_categories() -> list[KnowledgeCategory]:
    store = get_store()
    if hasattr(store, "list_knowledge_categories"):
        return store.list_knowledge_categories()
    return []


@router.post("/categories", response_model=KnowledgeCategory)
def create_knowledge_category(payload: KnowledgeCategoryCreate) -> KnowledgeCategory:
    return get_store().create_knowledge_category(payload)


@router.put("/categories/{category_id}", response_model=KnowledgeCategory)
def update_knowledge_category(
    category_id: str, payload: KnowledgeCategoryUpdate
) -> KnowledgeCategory:
    return get_store().update_knowledge_category(category_id, payload)


@router.post("", response_model=Document)
def create_document(payload: DocumentCreate) -> Document:
    store = get_store()
    project_id = payload.project_id
    if not project_id and hasattr(store, "list_projects"):
        general_project = next(
            (project for project in store.list_projects() if project.is_general), None
        )
        project_id = general_project.id if general_project else DEFAULT_GENERAL_PROJECT_ID
    normalized = payload.model_copy(update={"project_id": project_id})
    return store.create_document(normalized)


@router.post("/text", response_model=Document)
async def create_text_document(payload: DocumentTextCreate) -> Document:
    settings.ensure_local_dirs()
    store = get_store()
    document = store.create_document(
        DocumentCreate(
            title=payload.title,
            source_type=payload.source_type,
            category_id=payload.category_id,
            folder_id=payload.folder_id,
            pinned=payload.pinned,
            tags=payload.tags,
            project_id=payload.project_id
            or (
                next((project.id for project in store.list_projects() if project.is_general), None)
                if hasattr(store, "list_projects")
                else DEFAULT_GENERAL_PROJECT_ID
            ),
            metadata={
                **payload.metadata,
                "bytes": len(payload.content.encode("utf-8")),
                "ingest_mode": "text",
            },
        )
    )
    storage_path = (
        settings.files_dir / f"{document.id}{extension_for_source_type(payload.source_type)}"
    )
    storage_path.write_text(payload.content, encoding="utf-8")

    document.storage_path = str(Path(storage_path))
    document.updated_at = now_utc()
    try:
        document = await index_document_content(document, payload.content)
    except Exception as exc:
        metadata = dict(document.metadata) if isinstance(document.metadata, dict) else {}
        metadata["index_error"] = str(exc)[:240]
        document = document.model_copy(
            update={
                "indexed": False,
                "index_status": JobStatus.failed,
                "metadata": metadata,
                "updated_at": now_utc(),
            }
        )

    if hasattr(store, "update_document"):
        return store.update_document(document)
    return document


@router.post("/from-file", response_model=Document)
async def create_document_from_file(payload: DocumentFromFileCreate) -> Document:
    store = get_store()
    platform_file = store.get_platform_file(payload.file_id)
    if platform_file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    resolved_project_id = payload.project_id or (
        next((project.id for project in store.list_projects() if project.is_general), None)
        if hasattr(store, "list_projects")
        else DEFAULT_GENERAL_PROJECT_ID
    )
    document = ensure_document_for_platform_file(
        store,
        platform_file,
        project_id=resolved_project_id,
        folder_id=payload.folder_id,
        category_id=payload.category_id,
        pinned=payload.pinned,
        tags=payload.tags,
        metadata={"ingest_mode": "from_file", **payload.metadata},
        force_status_pending=True,
    )
    enqueue_platform_file_index(platform_file.id)
    return document


@router.post("/search", response_model=list[DocumentSearchResult])
async def search_documents(payload: DocumentSearchRequest) -> list[DocumentSearchResult]:
    store = get_store()
    documents = store.list_documents()
    documents_by_id = {document.id: document for document in documents}
    allowed_document_ids: set[str] | None = None
    if payload.knowledge_base_ids and hasattr(store, "list_knowledge_base_documents"):
        allowed_document_ids = {
            item.document_id
            for item in store.list_knowledge_base_documents()
            if item.enabled and item.knowledge_base_id in payload.knowledge_base_ids
        }
        if not allowed_document_ids:
            return []

    vector_store = QdrantVectorStore()
    try:
        results = await vector_store.search(
            DOCUMENT_COLLECTION,
            embed_text(payload.query),
            max(payload.limit * 4, payload.limit),
            payload_filter=_vector_payload_filter(
                document_ids=allowed_document_ids,
                folder_ids=payload.folder_ids,
                category_ids=payload.category_ids,
                tags=payload.tags,
                source_types=payload.source_types,
            ),
        )
    except Exception:
        results = []
    matches: list[DocumentSearchResult] = []
    seen_document_ids: set[str] = set()
    general_project_ids = {None, "", DEFAULT_GENERAL_PROJECT_ID}
    for item in results:
        raw_payload = item.get("payload") or {}
        raw_document_id = str(raw_payload.get("document_id") or "")
        if allowed_document_ids is not None and raw_document_id not in allowed_document_ids:
            continue
        raw_project_id = raw_payload.get("project_id")
        if payload.project_scope_mode == "global_only":
            if raw_project_id not in general_project_ids:
                continue
        elif payload.project_scope_mode == "project_only":
            if payload.project_id:
                if raw_project_id != payload.project_id:
                    continue
            elif raw_project_id not in general_project_ids:
                continue
        elif payload.project_scope_mode == "project_plus_global":
            if payload.project_id:
                if raw_project_id not in {payload.project_id, None, "", DEFAULT_GENERAL_PROJECT_ID}:
                    continue
            elif raw_project_id not in general_project_ids:
                continue
        if payload.folder_ids and raw_payload.get("folder_id") not in payload.folder_ids:
            continue
        if payload.category_ids and raw_payload.get("category_id") not in payload.category_ids:
            continue
        if payload.tags and not set(payload.tags).intersection(set(raw_payload.get("tags") or [])):
            continue
        if payload.source_types and raw_payload.get("source_type") not in payload.source_types:
            continue
        source_document = documents_by_id.get(raw_document_id)
        if source_document is not None:
            if payload.created_after and source_document.created_at < payload.created_after:
                continue
            if payload.created_before and source_document.created_at > payload.created_before:
                continue
        keyword_score = _keyword_score(
            payload.query,
            str(raw_payload.get("title") or ""),
            str(raw_payload.get("content") or ""),
            " ".join(str(tag) for tag in raw_payload.get("tags") or []),
        )
        combined_score = (float(item.get("score", 0)) * 0.75) + (keyword_score * 0.25)
        seen_document_ids.add(raw_document_id)
        matches.append(
            DocumentSearchResult(
                document_id=raw_payload.get("document_id", ""),
                title=raw_payload.get("title", "Documento"),
                score=round(combined_score, 6),
                content=raw_payload.get("content", ""),
                metadata={
                    "chunk_index": raw_payload.get("chunk_index"),
                    "summary": raw_payload.get("summary"),
                    "source_type": raw_payload.get("source_type"),
                    "category_id": raw_payload.get("category_id"),
                    "folder_id": raw_payload.get("folder_id"),
                    "project_id": raw_payload.get("project_id"),
                    "tags": raw_payload.get("tags") or [],
                    "match_mode": "hybrid",
                },
            )
        )
        if len(matches) >= payload.limit:
            break

    if len(matches) < payload.limit:
        for document in documents:
            if document.id in seen_document_ids:
                continue
            if allowed_document_ids is not None and document.id not in allowed_document_ids:
                continue
            if payload.source_types and document.source_type not in payload.source_types:
                continue
            if payload.folder_ids and document.folder_id not in payload.folder_ids:
                continue
            if payload.category_ids and document.category_id not in payload.category_ids:
                continue
            if payload.tags and not set(payload.tags).intersection(set(document.tags)):
                continue
            if payload.created_after and document.created_at < payload.created_after:
                continue
            if payload.created_before and document.created_at > payload.created_before:
                continue
            if payload.project_scope_mode == "global_only":
                if document.project_id not in general_project_ids:
                    continue
            elif payload.project_scope_mode == "project_only":
                if payload.project_id:
                    if document.project_id != payload.project_id:
                        continue
                elif document.project_id not in general_project_ids:
                    continue
            elif payload.project_scope_mode == "project_plus_global":
                if payload.project_id:
                    if document.project_id not in {
                        payload.project_id,
                        None,
                        "",
                        DEFAULT_GENERAL_PROJECT_ID,
                    }:
                        continue
                elif document.project_id not in general_project_ids:
                    continue

            score = _keyword_score(
                payload.query,
                document.title,
                document.source_type,
                " ".join(document.tags),
            )
            if score <= 0:
                continue
            matches.append(
                DocumentSearchResult(
                    document_id=document.id,
                    title=document.title,
                    score=round(score * 0.5, 6),
                    content="",
                    metadata={
                        "source_type": document.source_type,
                        "category_id": document.category_id,
                        "folder_id": document.folder_id,
                        "project_id": document.project_id,
                        "tags": document.tags,
                        "match_mode": "metadata",
                    },
                )
            )
            if len(matches) >= payload.limit:
                break

    return sorted(matches, key=lambda item: item.score, reverse=True)[: payload.limit]
