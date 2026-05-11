from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.contracts import (
    DEFAULT_GENERAL_PROJECT_ID,
    ChatGPTImportJob,
    PlatformFileCreate,
    PlatformFileUpdate,
)
from app.files.library import (
    content_type_for_name,
    counted_filename,
    find_duplicate,
    is_zip_storage_path,
    register_zip_entries_as_platform_files,
    safe_filename,
)
from app.rag.indexing import ensure_document_for_platform_file
from app.storage.store import get_store
from app.workers.import_queue import enqueue_chatgpt_import_job
from app.workers.index_queue import (
    INDEX_PRIORITY_BACKGROUND,
    enqueue_platform_file_index,
    enqueue_platform_file_indexes,
)

router = APIRouter()
UPLOAD_CHUNK_BYTES = 1024 * 1024


def _safe_filename(filename: str) -> str:
    return safe_filename(filename or "chatgpt-export")


@router.post("/chatgpt", response_model=ChatGPTImportJob, status_code=status.HTTP_202_ACCEPTED)
async def import_chatgpt(file: UploadFile = File(...)) -> ChatGPTImportJob:
    filename = _safe_filename(file.filename or "chatgpt-export")
    if not filename.lower().endswith((".json", ".zip")):
        raise HTTPException(
            status_code=400,
            detail="Envie o conversations.json ou o .zip de exportação do ChatGPT.",
        )

    settings.ensure_local_dirs()
    job = ChatGPTImportJob(
        source_filename=filename,
        file_path="",
        file_size_bytes=0,
        total_bytes=None,
        current_step="Recebendo upload",
    )
    job_dir = settings.imports_dir / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    target_path = job_dir / filename

    size = 0
    checksum = hashlib.sha256()
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
    finally:
        await file.close()

    store = get_store()
    job.file_path = str(target_path)
    job.file_size_bytes = size
    job.total_bytes = size
    existing_files = store.list_platform_files()
    checksum_hex = checksum.hexdigest()
    duplicate = find_duplicate(
        existing_files,
        filename=filename,
        size_bytes=size,
        checksum_sha256=checksum_hex,
    )
    display_filename = counted_filename(
        filename,
        {platform_file.filename for platform_file in existing_files if platform_file.filename},
    )
    platform_file = store.create_platform_file(
        PlatformFileCreate(
            filename=display_filename,
            original_filename=filename,
            content_type=file.content_type or content_type_for_name(filename),
            size_bytes=size,
            storage_path=str(target_path),
            checksum_sha256=checksum_hex,
            duplicate_of_id=duplicate.id if duplicate else None,
            source="chatgpt_import",
            tags=["chatgpt-export"],
            metadata={
                "job_id": job.id,
                "project_id": DEFAULT_GENERAL_PROJECT_ID,
            },
        )
    )
    ensure_document_for_platform_file(
        store,
        platform_file,
        force_status_pending=True,
    )
    enqueue_platform_file_index(platform_file.id, priority=INDEX_PRIORITY_BACKGROUND)
    if filename.lower().endswith(".zip"):
        registered_entry_files = register_zip_entries_as_platform_files(
            archive_path=target_path,
            archive_file=platform_file,
            store=store,
            job_id=job.id,
        )
        if registered_entry_files:
            for entry_file in registered_entry_files:
                ensure_document_for_platform_file(
                    store,
                    entry_file,
                    force_status_pending=True,
                )
            enqueue_platform_file_indexes(
                [entry_file.id for entry_file in registered_entry_files],
                priority=INDEX_PRIORITY_BACKGROUND,
            )
            platform_file = store.update_platform_file(
                platform_file.id,
                PlatformFileUpdate(
                    metadata={
                        **platform_file.metadata,
                        "registered_zip_entries": len(registered_entry_files),
                    }
                ),
            )
    job.platform_file_id = platform_file.id
    job.current_step = "Upload recebido; importação na fila"
    store.upsert_import_job(job)
    enqueue_chatgpt_import_job(job.id)
    return job


@router.post(
    "/chatgpt/from-file/{file_id}",
    response_model=ChatGPTImportJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_chatgpt_from_existing_file(
    file_id: str,
) -> ChatGPTImportJob:
    store = get_store()
    platform_file = store.get_platform_file(file_id)
    if platform_file is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    if is_zip_storage_path(platform_file.storage_path):
        raise HTTPException(
            status_code=400,
            detail="Escolha o ZIP exportado, não um item interno dele.",
        )

    filename = _safe_filename(platform_file.original_filename or platform_file.filename)
    if not filename.lower().endswith((".json", ".zip")):
        raise HTTPException(
            status_code=400,
            detail="O arquivo existente precisa ser conversations.json ou o .zip de exportação.",
        )

    file_path = Path(platform_file.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado.")

    ensure_document_for_platform_file(
        store,
        platform_file,
        force_status_pending=True,
    )
    enqueue_platform_file_index(platform_file.id, priority=INDEX_PRIORITY_BACKGROUND)

    job = ChatGPTImportJob(
        source_filename=filename,
        file_path=str(file_path),
        platform_file_id=platform_file.id,
        file_size_bytes=platform_file.size_bytes,
        total_bytes=platform_file.size_bytes,
        current_step="Importação existente na fila",
    )
    if filename.lower().endswith(".zip"):
        registered_entry_files = register_zip_entries_as_platform_files(
            archive_path=file_path,
            archive_file=platform_file,
            store=store,
            job_id=job.id,
        )
        if registered_entry_files:
            for entry_file in registered_entry_files:
                ensure_document_for_platform_file(
                    store,
                    entry_file,
                    force_status_pending=True,
                )
            enqueue_platform_file_indexes(
                [entry_file.id for entry_file in registered_entry_files],
                priority=INDEX_PRIORITY_BACKGROUND,
            )
            store.update_platform_file(
                platform_file.id,
                PlatformFileUpdate(
                    metadata={
                        **platform_file.metadata,
                        "registered_zip_entries": len(registered_entry_files),
                    }
                ),
            )
    store.upsert_import_job(job)
    enqueue_chatgpt_import_job(job.id)
    return job


@router.get("/chatgpt/jobs", response_model=list[ChatGPTImportJob])
def list_chatgpt_import_jobs() -> list[ChatGPTImportJob]:
    return get_store().list_import_jobs()


@router.get("/chatgpt/jobs/{job_id}", response_model=ChatGPTImportJob)
def get_chatgpt_import_job(job_id: str) -> ChatGPTImportJob:
    job = get_store().get_import_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job de importação não encontrado.")
    return job
