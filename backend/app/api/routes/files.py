from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    PlatformFile,
    PlatformFileCreate,
    PlatformFileIndexingStatus,
    PlatformFilePage,
    PlatformFileUpdate,
)
from app.files.library import (
    content_type_for_name,
    counted_filename,
    find_duplicate,
    is_zip_storage_path,
    parse_zip_storage_path,
    safe_filename,
)
from app.rag.indexing import (
    delete_documents_for_platform_file,
    ensure_document_for_platform_file,
)
from app.storage.store import get_store
from app.workers.index_queue import (
    enqueue_platform_file_index,
    get_platform_file_indexing_status,
)

router = APIRouter()
UPLOAD_CHUNK_BYTES = 1024 * 1024
FileSource = Literal["upload", "chat_attachment", "chatgpt_import", "generated", "knowledge_base"]


def _all_files() -> list[PlatformFile]:
    store = get_store()
    if hasattr(store, "list_platform_files"):
        return store.list_platform_files()
    return []


def _matches_file_filters(
    platform_file: PlatformFile,
    *,
    source: FileSource | None,
    query: str | None,
    project_id: str | None,
    folder_id: str | None,
) -> bool:
    if source and platform_file.source != source:
        return False
    metadata = dict(platform_file.metadata) if isinstance(platform_file.metadata, dict) else {}
    if project_id and str(metadata.get("project_id") or "") != project_id:
        return False
    if folder_id and str(metadata.get("folder_id") or "") != folder_id:
        return False
    if query:
        normalized_query = query.strip().lower()
        if normalized_query:
            haystack = " ".join(
                item.lower()
                for item in [platform_file.filename, platform_file.original_filename]
                if item
            )
            if normalized_query not in haystack:
                return False
    return True


def _content_disposition_inline(filename: str) -> str:
    """Monta um Content-Disposition seguro (sem CR/LF/aspas) com fallback RFC 5987."""
    name = safe_filename(filename) or "arquivo"
    # Remove caracteres de controle e aspas que permitiriam header-splitting/spoofing.
    ascii_name = re.sub(r'[\r\n"\x00-\x1f\x7f]', "", name) or "arquivo"
    encoded = quote(name, safe="")
    return f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def _safe_local_path(storage_path: str) -> Path:
    path = Path(storage_path).resolve()
    data_dir = settings.data_dir.resolve()
    if not path.is_relative_to(data_dir):
        raise HTTPException(status_code=403, detail="Arquivo fora do storage local.")
    return path


def _iter_zip_entry(storage_path: str):
    archive_path, entry_name = parse_zip_storage_path(storage_path)
    archive_path = _safe_local_path(str(archive_path))
    with zipfile.ZipFile(archive_path) as archive:
        with archive.open(entry_name) as handle:
            while chunk := handle.read(UPLOAD_CHUNK_BYTES):
                yield chunk


def _maybe_delete_local_storage(platform_file: PlatformFile, all_files: list[PlatformFile]) -> None:
    if is_zip_storage_path(platform_file.storage_path):
        return
    if any(
        item.metadata.get("archive_file_id") == platform_file.id
        for item in all_files
        if item.id != platform_file.id
    ):
        return
    path = _safe_local_path(platform_file.storage_path)
    if path.is_file():
        path.unlink(missing_ok=True)


@router.get("", response_model=list[PlatformFile])
def list_files(
    source: FileSource | None = None,
    query: str | None = None,
    project_id: str | None = None,
    folder_id: str | None = None,
) -> list[PlatformFile]:
    files = _all_files()
    filtered = [
        platform_file
        for platform_file in files
        if _matches_file_filters(
            platform_file,
            source=source,
            query=query,
            project_id=project_id,
            folder_id=folder_id,
        )
    ]
    return sorted(filtered, key=lambda item: item.created_at, reverse=True)


@router.get("/page", response_model=PlatformFilePage)
def list_files_page(
    limit: int = 50,
    offset: int = 0,
    source: FileSource | None = None,
    query: str | None = None,
    project_id: str | None = None,
    folder_id: str | None = None,
) -> PlatformFilePage:
    normalized_limit = max(1, min(int(limit), 200))
    normalized_offset = max(0, int(offset))
    filtered = list_files(
        source=source,
        query=query,
        project_id=project_id,
        folder_id=folder_id,
    )
    total = len(filtered)
    items = filtered[normalized_offset : normalized_offset + normalized_limit]
    return PlatformFilePage(
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
        has_more=(normalized_offset + len(items)) < total,
    )


@router.get("/indexing/status", response_model=PlatformFileIndexingStatus)
def file_indexing_status() -> PlatformFileIndexingStatus:
    return get_platform_file_indexing_status()


@router.post("/upload", response_model=PlatformFile, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    source: FileSource = "upload",
    project_id: str | None = None,
    folder_id: str | None = None,
    session_id: str | None = None,
) -> PlatformFile:
    original_filename = safe_filename(file.filename or "arquivo")
    settings.ensure_local_dirs()
    store = get_store()

    platform_file = PlatformFile(
        filename=original_filename,
        original_filename=original_filename,
        content_type=file.content_type or content_type_for_name(original_filename),
        size_bytes=0,
        storage_path="",
        source=source,
        metadata={},
    )
    target_dir = settings.files_dir / "library" / platform_file.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / original_filename

    checksum = hashlib.sha256()
    size = 0
    try:
        with target_path.open("wb") as output:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > settings.max_import_bytes:
                    target_path.unlink(missing_ok=True)
                    limit_gb = settings.max_import_bytes / 1024 / 1024 / 1024
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Arquivo maior que {limit_gb:.0f} GB.",
                    )
                checksum.update(chunk)
                output.write(chunk)
    except BaseException:
        # Limpa o diretório por-arquivo recém-criado quando o upload falha
        # antes de o PlatformFile ser persistido (evita inodes órfãos).
        shutil.rmtree(target_dir, ignore_errors=True)
        raise
    finally:
        await file.close()

    existing_files = _all_files()
    checksum_hex = checksum.hexdigest()
    duplicate = find_duplicate(
        existing_files,
        filename=original_filename,
        size_bytes=size,
        checksum_sha256=checksum_hex,
    )
    display_filename = counted_filename(
        original_filename,
        {platform_file.filename for platform_file in existing_files if platform_file.filename},
    )

    resolved_project_id = project_id
    if not resolved_project_id and hasattr(store, "list_projects"):
        general = next((project for project in store.list_projects() if project.is_general), None)
        resolved_project_id = general.id if general else DEFAULT_GENERAL_PROJECT_ID
    if not resolved_project_id:
        resolved_project_id = DEFAULT_GENERAL_PROJECT_ID

    payload = PlatformFileCreate(
        filename=display_filename,
        original_filename=original_filename,
        content_type=file.content_type or content_type_for_name(original_filename),
        size_bytes=size,
        storage_path=str(target_path),
        checksum_sha256=checksum_hex,
        duplicate_of_id=duplicate.id if duplicate else None,
        source=source,
        metadata={
            "upload_mode": "chunked",
            "original_upload_filename": original_filename,
            "project_id": resolved_project_id,
            "folder_id": folder_id,
            "session_id": session_id,
        },
    )
    created = store.create_platform_file(payload)
    ensure_document_for_platform_file(
        store,
        created,
        project_id=resolved_project_id,
        folder_id=folder_id,
        metadata={"session_id": session_id} if session_id else None,
        force_status_pending=True,
    )
    enqueue_platform_file_index(created.id)
    return created


@router.get("/{file_id}/content")
def get_file_content(file_id: str):
    platform_file = get_store().get_platform_file(file_id)
    if platform_file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    media_type = platform_file.content_type or content_type_for_name(platform_file.filename)
    if is_zip_storage_path(platform_file.storage_path):
        archive_path, entry_name = parse_zip_storage_path(platform_file.storage_path)
        archive_path = _safe_local_path(str(archive_path))
        try:
            with zipfile.ZipFile(archive_path) as archive:
                archive.getinfo(entry_name)
        except (FileNotFoundError, KeyError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=404, detail="Item do ZIP não encontrado.") from exc
        return StreamingResponse(
            _iter_zip_entry(platform_file.storage_path),
            media_type=media_type,
            headers={
                "Content-Disposition": _content_disposition_inline(platform_file.filename)
            },
        )

    path = _safe_local_path(platform_file.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado.")
    return FileResponse(
        path,
        media_type=media_type,
        filename=platform_file.filename,
        content_disposition_type="inline",
    )


@router.put("/{file_id}", response_model=PlatformFile)
def update_file(file_id: str, payload: PlatformFileUpdate) -> PlatformFile:
    store = get_store()
    existing = store.get_platform_file(file_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    if payload.filename:
        other_names = {
            platform_file.filename
            for platform_file in _all_files()
            if platform_file.id != file_id and platform_file.filename
        }
        payload.filename = counted_filename(payload.filename, other_names)
    try:
        updated = store.update_platform_file(file_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.") from exc
    metadata = dict(updated.metadata) if isinstance(updated.metadata, dict) else {}
    metadata_project_id = metadata.get("project_id")
    metadata_folder_id = metadata.get("folder_id")
    ensure_document_for_platform_file(
        store,
        updated,
        project_id=metadata_project_id if isinstance(metadata_project_id, str) else None,
        folder_id=metadata_folder_id if isinstance(metadata_folder_id, str) else None,
        force_status_pending=True,
    )
    enqueue_platform_file_index(updated.id)
    return updated


@router.delete("/{file_id}", response_model=PlatformFile)
def delete_file(file_id: str) -> PlatformFile:
    store = get_store()
    all_files = _all_files()
    deleted = store.delete_platform_file(file_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    _maybe_delete_local_storage(deleted, all_files)
    delete_documents_for_platform_file(store, file_id)
    return deleted
