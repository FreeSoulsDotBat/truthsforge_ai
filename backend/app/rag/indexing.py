from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    Document,
    DocumentCreate,
    JobStatus,
    PlatformFile,
    now_utc,
)
from app.files.processor import (
    chunk_text,
    detect_source_type,
    extract_text_content,
    summarize_chunk,
)
from app.rag.embeddings import embed_text, embedding_backend_name, embedding_model_name
from app.rag.vector_store import QdrantVectorStore

DOCUMENT_COLLECTION = "truths_forge_documents"
EXTRACTABLE_SOURCE_TYPES = {"markdown", "txt", "csv", "html", "pdf", "docx", "image", "unknown"}
MAX_SYNC_TEXT_INDEX_BYTES = 20 * 1024 * 1024
MAX_INDEX_CHARS = 250_000
FALLBACK_TAG = "arquivo"


def _parse_datetime(value: object) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        normalized = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _status_rank(status: JobStatus | str) -> int:
    if status == JobStatus.running:
        return 4
    if status == JobStatus.pending:
        return 3
    if status == JobStatus.failed:
        return 2
    if status == JobStatus.completed:
        return 1
    return 0


def _general_project_id(store) -> str:
    if hasattr(store, "list_projects"):
        projects = store.list_projects()
        general = next((project for project in projects if project.is_general), None)
        if general is not None:
            return general.id
    return DEFAULT_GENERAL_PROJECT_ID


def _is_text_like(platform_file: PlatformFile, source_type: str) -> bool:
    if source_type in EXTRACTABLE_SOURCE_TYPES:
        return True
    if platform_file.content_type and platform_file.content_type.startswith("text/"):
        return True
    name = (platform_file.original_filename or platform_file.filename).lower()
    return name.endswith((".json", ".yaml", ".yml", ".xml", ".log"))


def _normalize_tags(*groups: list[str]) -> list[str]:
    normalized: list[str] = []
    for group in groups:
        for raw in group:
            tag = raw.strip()
            if not tag or tag in normalized:
                continue
            normalized.append(tag)
    if FALLBACK_TAG not in normalized:
        normalized.append(FALLBACK_TAG)
    return normalized


def _document_for_file(store, file_id: str) -> Document | None:
    if not hasattr(store, "list_documents"):
        return None
    selected: Document | None = None
    selected_key: tuple[datetime, int, str] | None = None
    for document in store.list_documents():
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        if metadata.get("file_id") == file_id:
            candidate_key = (
                _parse_datetime(document.updated_at),
                _status_rank(document.index_status),
                document.id,
            )
            if selected is None or selected_key is None or candidate_key > selected_key:
                selected = document
                selected_key = candidate_key
    return selected


def ensure_document_for_platform_file(
    store,
    platform_file: PlatformFile,
    *,
    project_id: str | None = None,
    folder_id: str | None = None,
    category_id: str | None = None,
    tags: list[str] | None = None,
    pinned: bool | None = None,
    metadata: dict[str, Any] | None = None,
    force_status_pending: bool = False,
) -> Document:
    source_type = detect_source_type(platform_file.original_filename or platform_file.filename)
    file_metadata = dict(platform_file.metadata) if isinstance(platform_file.metadata, dict) else {}
    resolved_project_id = (
        project_id
        or file_metadata.get("project_id")
        or _general_project_id(store)
        or DEFAULT_GENERAL_PROJECT_ID
    )
    resolved_folder_id = folder_id if folder_id is not None else file_metadata.get("folder_id")
    metadata_seed = metadata if isinstance(metadata, dict) else {}
    merged_metadata: dict[str, Any] = {
        **metadata_seed,
        "file_id": platform_file.id,
        "file_source": platform_file.source,
        "bytes": platform_file.size_bytes,
    }
    merged_metadata.setdefault("ingest_mode", "auto_file")
    if file_metadata.get("session_id"):
        merged_metadata["session_id"] = file_metadata["session_id"]
    if file_metadata.get("zip_entry"):
        merged_metadata["zip_entry"] = file_metadata["zip_entry"]

    existing = _document_for_file(store, platform_file.id)
    resolved_category_id = (
        category_id if category_id is not None else (existing.category_id if existing else None)
    )
    normalized_tags = _normalize_tags(
        tags or [],
        platform_file.tags,
        existing.tags if existing else [],
    )

    if existing is None:
        created = store.create_document(
            DocumentCreate(
                title=platform_file.original_filename,
                source_type=source_type,  # type: ignore[arg-type]
                original_path=platform_file.original_filename,
                category_id=resolved_category_id,
                folder_id=resolved_folder_id,
                pinned=bool(pinned) if pinned is not None else False,
                tags=normalized_tags,
                project_id=resolved_project_id,
                metadata=merged_metadata,
            )
        )
        created.storage_path = platform_file.storage_path
        if force_status_pending:
            created.indexed = False
            created.index_status = JobStatus.pending
        created.updated_at = now_utc()
        if hasattr(store, "update_document"):
            created = store.update_document(created)
        return created

    updates: dict[str, Any] = {
        "title": platform_file.original_filename,
        "source_type": source_type,
        "original_path": platform_file.original_filename,
        "storage_path": platform_file.storage_path,
        "category_id": resolved_category_id,
        "folder_id": resolved_folder_id,
        "project_id": resolved_project_id,
        "tags": normalized_tags,
        "metadata": {
            **(existing.metadata if isinstance(existing.metadata, dict) else {}),
            **merged_metadata,
        },
        "updated_at": now_utc(),
    }
    if pinned is not None:
        updates["pinned"] = pinned
    if force_status_pending:
        updates["indexed"] = False
        updates["index_status"] = JobStatus.pending

    updated = existing.model_copy(update=updates)
    if hasattr(store, "update_document"):
        updated = store.update_document(updated)
    return updated


def _fallback_document_text(document: Document, platform_file: PlatformFile) -> str:
    tags = ", ".join(document.tags) if document.tags else "sem tags"
    folder = document.folder_id or "raiz"
    lines = [
        f"Arquivo da plataforma: {platform_file.original_filename}",
        f"Tipo detectado: {document.source_type}",
        f"Origem: {platform_file.source}",
        f"Projeto: {document.project_id or DEFAULT_GENERAL_PROJECT_ID}",
        f"Pasta: {folder}",
        f"Tags: {tags}",
    ]
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    zip_entry = metadata.get("zip_entry")
    if isinstance(zip_entry, str) and zip_entry.strip():
        lines.append(f"Entrada ZIP: {zip_entry.strip()}")
    return "\n".join(lines).strip()


def _content_for_platform_file(
    document: Document, platform_file: PlatformFile
) -> tuple[str, str, list[str]]:
    source_type = str(document.source_type)
    extraction_warnings: list[str] = []
    if _is_text_like(platform_file, source_type):
        extraction = extract_text_content(
            platform_file.storage_path,
            settings.data_dir,
            source_type,
            max_chars=MAX_INDEX_CHARS,
        )
        text_content = extraction.text.strip()
        extraction_warnings = extraction.warnings
        if text_content:
            return text_content, extraction.mode, extraction_warnings
    return (
        _fallback_document_text(document, platform_file),
        "metadata_fallback",
        extraction_warnings,
    )


async def delete_document_vectors(document_id: str) -> None:
    vector_store = QdrantVectorStore()
    await vector_store.delete_document_chunks(DOCUMENT_COLLECTION, document_id)


async def index_document_content(document: Document, content: str) -> Document:
    chunks = chunk_text(content)
    if not chunks:
        chunks = [content.strip()]
    vector_store = QdrantVectorStore()
    await vector_store.delete_document_chunks(DOCUMENT_COLLECTION, document.id)
    payloads = [
        {
            "id": f"{document.id}:{index}",
            "vector": embed_text(chunk),
            "payload": {
                "document_id": document.id,
                "title": document.title,
                "content": chunk,
                "summary": summarize_chunk(chunk),
                "chunk_index": index,
                "project_id": document.project_id,
                "category_id": document.category_id,
                "folder_id": document.folder_id,
                "pinned": document.pinned,
                "tags": document.tags,
                "source_type": document.source_type,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "file_id": (
                    document.metadata.get("file_id")
                    if isinstance(document.metadata, dict)
                    else None
                ),
            },
        }
        for index, chunk in enumerate(chunks)
    ]
    await vector_store.upsert_chunks(DOCUMENT_COLLECTION, payloads)
    metadata = dict(document.metadata) if isinstance(document.metadata, dict) else {}
    metadata["chunk_count"] = len(chunks)
    metadata["embedding_backend"] = embedding_backend_name()
    metadata["embedding_model"] = embedding_model_name()
    metadata["embedding_dimensions"] = len(payloads[0]["vector"]) if payloads else 0
    metadata.pop("index_error", None)
    metadata.pop("index_note", None)
    return document.model_copy(
        update={
            "indexed": True,
            "index_status": JobStatus.completed,
            "metadata": metadata,
            "updated_at": now_utc(),
        }
    )


async def index_platform_file_document(
    store,
    *,
    document: Document,
    platform_file: PlatformFile,
) -> Document:
    running = document.model_copy(
        update={
            "indexed": False,
            "index_status": JobStatus.running,
            "metadata": {
                **(document.metadata if isinstance(document.metadata, dict) else {}),
                "index_attempts": int(
                    (document.metadata if isinstance(document.metadata, dict) else {}).get(
                        "index_attempts", 0
                    )
                )
                + 1,
                "index_started_at": now_utc().isoformat(),
            },
            "updated_at": now_utc(),
        }
    )
    if hasattr(store, "update_document"):
        running = store.update_document(running)

    try:
        content, mode, extraction_warnings = _content_for_platform_file(running, platform_file)
        indexed = await index_document_content(running, content)
        metadata = dict(indexed.metadata) if isinstance(indexed.metadata, dict) else {}
        metadata["index_content_mode"] = mode
        metadata["index_chars"] = len(content)
        metadata["index_completed_at"] = now_utc().isoformat()
        metadata["index_retryable"] = False
        if extraction_warnings:
            metadata["index_warnings"] = extraction_warnings
        else:
            metadata.pop("index_warnings", None)
        updated = indexed.model_copy(
            update={
                "storage_path": platform_file.storage_path,
                "metadata": metadata,
                "updated_at": now_utc(),
            }
        )
        if hasattr(store, "update_document"):
            updated = store.update_document(updated)
        return updated
    except Exception as exc:
        metadata = dict(running.metadata) if isinstance(running.metadata, dict) else {}
        metadata["index_error"] = str(exc)[:240]
        metadata["index_failed_at"] = now_utc().isoformat()
        metadata["index_retryable"] = True
        failed = running.model_copy(
            update={
                "indexed": False,
                "index_status": JobStatus.failed,
                "metadata": metadata,
                "updated_at": now_utc(),
            }
        )
        if hasattr(store, "update_document"):
            failed = store.update_document(failed)
        return failed


def process_platform_file_index(file_id: str) -> Document | None:
    from app.storage.store import get_store

    store = get_store()
    if not hasattr(store, "get_platform_file"):
        return None
    platform_file = store.get_platform_file(file_id)
    if platform_file is None:
        return None
    document = ensure_document_for_platform_file(
        store,
        platform_file,
        force_status_pending=True,
    )
    return asyncio.run(
        index_platform_file_document(store, document=document, platform_file=platform_file)
    )


def delete_documents_for_platform_file(store, file_id: str) -> list[str]:
    if not hasattr(store, "list_documents") or not hasattr(store, "delete_document"):
        return []
    deleted_ids: list[str] = []
    for document in store.list_documents():
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        if metadata.get("file_id") != file_id:
            continue
        try:
            asyncio.run(delete_document_vectors(document.id))
        except Exception:
            pass
        deleted = store.delete_document(document.id)
        if deleted is not None:
            deleted_ids.append(deleted.id)
    return deleted_ids
