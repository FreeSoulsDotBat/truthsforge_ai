from __future__ import annotations

import json
from pathlib import Path

from app.audit.service import record_audit_event
from app.core.contracts import AuditEvent, JobStatus, now_utc
from app.importers.chatgpt import ChatGPTImportError, import_chatgpt_export_from_path
from app.storage.store import get_store


def _progress_percent(processed_bytes: int, total_bytes: int | None) -> float:
    if not total_bytes:
        return 0
    return min(99, round(processed_bytes / total_bytes * 100, 2))


def process_chatgpt_import_job(job_id: str) -> None:
    store = get_store()
    job = store.get_import_job(job_id)
    if job is None:
        return

    job.status = JobStatus.running
    job.current_step = "Processando conversations.json"
    job.progress_percent = 0
    store.upsert_import_job(job)

    def update_progress(processed_bytes: int, total_bytes: int | None, step: str) -> None:
        current = store.get_import_job(job_id)
        if current is None or current.status != JobStatus.running:
            return
        if total_bytes:
            current.total_bytes = total_bytes
        current.processed_bytes = max(current.processed_bytes, processed_bytes)
        current.progress_percent = _progress_percent(current.processed_bytes, current.total_bytes)
        current.current_step = step
        store.upsert_import_job(current)

    try:
        summary = import_chatgpt_export_from_path(
            Path(job.file_path),
            job.source_filename,
            store,
            progress=update_progress,
        )
        job = store.get_import_job(job_id) or job
        job.status = JobStatus.completed
        job.summary = summary
        job.error = None
        job.progress_percent = 100
        job.processed_bytes = job.total_bytes or job.file_size_bytes
        job.current_step = "Importação concluída"
        job.completed_at = now_utc()
        store.upsert_import_job(job)

        record_audit_event(
            AuditEvent(
                event_type="import.chatgpt",
                metadata={
                    "job_id": job.id,
                    "source_filename": summary.source_filename,
                    "file_size_bytes": job.file_size_bytes,
                    "conversations_found": summary.conversations_found,
                    "sessions_imported": summary.sessions_imported,
                    "sessions_skipped": summary.sessions_skipped,
                    "messages_imported": summary.messages_imported,
                    "messages_skipped": summary.messages_skipped,
                    "errors": summary.errors[:10],
                },
            )
        )
    except (ChatGPTImportError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        failed = store.get_import_job(job_id) or job
        failed.status = JobStatus.failed
        failed.error = str(exc)
        failed.current_step = "Falha na importação"
        failed.completed_at = now_utc()
        store.upsert_import_job(failed)
    except Exception as exc:
        failed = store.get_import_job(job_id) or job
        failed.status = JobStatus.failed
        failed.error = f"Falha inesperada na importação: {str(exc)[:300]}"
        failed.current_step = "Falha na importação"
        failed.completed_at = now_utc()
        store.upsert_import_job(failed)
