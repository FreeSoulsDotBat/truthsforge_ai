from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock, Thread
from time import monotonic

from app.core.contracts import JobStatus, PlatformFileIndexingStatus, now_utc
from app.rag.indexing import ensure_document_for_platform_file, process_platform_file_index
from app.storage.store import get_store
from app.workers.job_queue import create_job_queue

logger = logging.getLogger(__name__)

# Queue backend chosen by settings.queue_backend (memory|redis|valkey). The
# WORKER stays an in-process thread; only the QUEUE can move to Valkey/Redis
# so multiple backend replicas share one backlog (BZPOPMIN is atomic).
_queue = create_job_queue("index")
_thread_lock = Lock()
_worker_thread: Thread | None = None
_last_recovery_at: float = 0
_last_backfill_at: float = 0
_RECOVERY_INTERVAL_SECONDS = 20
_BACKFILL_INTERVAL_SECONDS = 30
_RECOVERY_MAX_ITEMS = 250
_BACKFILL_MAX_ITEMS = 250
INDEX_PRIORITY_NORMAL = 0
INDEX_PRIORITY_BACKGROUND = 10


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


def _priority_for_status(status: JobStatus | str) -> int:
    if status == JobStatus.running:
        return 4
    if status == JobStatus.pending:
        return 3
    if status == JobStatus.failed:
        return 2
    if status == JobStatus.completed:
        return 1
    return 0


def _document_status_by_file_id(store) -> dict[str, JobStatus | str]:
    if not hasattr(store, "list_documents"):
        return {}
    mapped: dict[str, tuple[JobStatus | str, tuple[datetime, int, str]]] = {}
    for document in store.list_documents():
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        file_id = metadata.get("file_id")
        if not isinstance(file_id, str) or not file_id.strip():
            continue
        candidate_key = (
            _parse_datetime(document.updated_at),
            _priority_for_status(document.index_status),
            document.id,
        )
        current = mapped.get(file_id)
        if current is None or candidate_key > current[1]:
            mapped[file_id] = (document.index_status, candidate_key)
    return {file_id: payload[0] for file_id, payload in mapped.items()}


def _mark_document_running_for_file_id(file_id: str) -> None:
    store = get_store()
    if not hasattr(store, "list_documents") or not hasattr(store, "update_document"):
        return
    candidate = None
    candidate_key = None
    for document in store.list_documents():
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        current_file_id = metadata.get("file_id")
        if current_file_id != file_id:
            continue
        if document.index_status != JobStatus.pending:
            continue
        document_key = (
            _parse_datetime(document.updated_at),
            _priority_for_status(document.index_status),
            document.id,
        )
        if candidate is None or document_key > candidate_key:
            candidate = document
            candidate_key = document_key
    if candidate is None:
        return
    store.update_document(
        candidate.model_copy(update={"index_status": JobStatus.running, "updated_at": now_utc()})
    )


def _worker_loop() -> None:
    global _last_recovery_at, _last_backfill_at
    while True:
        file_id = _queue.get(timeout=0.5)
        if file_id is None:
            now = monotonic()
            if now - _last_recovery_at >= _RECOVERY_INTERVAL_SECONDS:
                try:
                    recover_pending_platform_file_indexes()
                except Exception:
                    pass
                _last_recovery_at = now
            if now - _last_backfill_at >= _BACKFILL_INTERVAL_SECONDS:
                try:
                    backfill_missing_platform_file_indexes()
                except Exception:
                    pass
                _last_backfill_at = now
            continue
        retry_scheduled = False
        try:
            try:
                indexed = process_platform_file_index(file_id)
                if indexed is not None and indexed.index_status == JobStatus.failed:
                    metadata = dict(indexed.metadata) if isinstance(indexed.metadata, dict) else {}
                    attempts = int(metadata.get("index_attempts", 1))
                    retryable = bool(metadata.get("index_retryable", False))
                    if retryable and attempts < 3:
                        # Retry: re-add without releasing the dedup marker.
                        _queue.requeue(file_id, INDEX_PRIORITY_BACKGROUND + attempts)
                        retry_scheduled = True
            except Exception:
                # Erro inesperado FORA da indexacao (que ja captura suas proprias
                # falhas): nao deve derrubar a thread. Loga para diagnostico em
                # vez de mascarar; o item sera reavaliado pela varredura
                # periodica (recover/backfill) se o documento seguir pending.
                logger.exception("Falha inesperada ao indexar platform file %s", file_id)
        finally:
            if not retry_scheduled:
                _queue.release(file_id)


def _ensure_worker_thread() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    with _thread_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_thread = Thread(
            target=_worker_loop,
            name="truths-forge-file-indexer",
            daemon=True,
        )
        _worker_thread.start()


def enqueue_platform_file_index(file_id: str | None, priority: int = INDEX_PRIORITY_NORMAL) -> None:
    if not file_id:
        return
    _ensure_worker_thread()
    # Mark the document "running" BEFORE the item becomes visible on the queue,
    # so a worker blocked on ``_queue.get`` can't start processing before the
    # status is set (re-marking an already-queued file is harmless).
    if priority <= INDEX_PRIORITY_NORMAL:
        _mark_document_running_for_file_id(file_id)
    # ``put`` is dedup-guarded: returns False when the file is already queued
    # or in flight, so we don't re-enqueue it.
    _queue.put(file_id, priority)


def enqueue_platform_file_indexes(
    file_ids: list[str], priority: int = INDEX_PRIORITY_NORMAL
) -> None:
    for file_id in file_ids:
        enqueue_platform_file_index(file_id, priority=priority)


def recover_pending_platform_file_indexes(max_items: int = _RECOVERY_MAX_ITEMS) -> list[str]:
    store = get_store()
    if not hasattr(store, "list_documents"):
        return []
    status_by_file_id = _document_status_by_file_id(store)
    pending_file_ids = [
        file_id
        for file_id, status in status_by_file_id.items()
        if status in {JobStatus.pending, JobStatus.running}
    ][:max_items]
    enqueue_platform_file_indexes(pending_file_ids, priority=INDEX_PRIORITY_BACKGROUND)
    return pending_file_ids


def retry_failed_platform_file_indexes(max_items: int = _RECOVERY_MAX_ITEMS) -> list[str]:
    store = get_store()
    if not hasattr(store, "list_documents"):
        return []
    failed_file_ids: list[str] = []
    for document in store.list_documents():
        if document.index_status != JobStatus.failed:
            continue
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        file_id = metadata.get("file_id")
        attempts = int(metadata.get("index_attempts", 0))
        if isinstance(file_id, str) and attempts < 3:
            failed_file_ids.append(file_id)
        if len(failed_file_ids) >= max_items:
            break
    enqueue_platform_file_indexes(failed_file_ids, priority=INDEX_PRIORITY_BACKGROUND)
    return failed_file_ids


def backfill_missing_platform_file_indexes(max_items: int = _BACKFILL_MAX_ITEMS) -> list[str]:
    store = get_store()
    if not hasattr(store, "list_platform_files"):
        return []
    known_status = _document_status_by_file_id(store)
    to_queue: list[str] = []
    for platform_file in store.list_platform_files():
        if platform_file.id in known_status:
            continue
        ensure_document_for_platform_file(store, platform_file, force_status_pending=True)
        to_queue.append(platform_file.id)
        if len(to_queue) >= max_items:
            break
    enqueue_platform_file_indexes(to_queue, priority=INDEX_PRIORITY_BACKGROUND)
    return to_queue


def get_platform_file_indexing_status() -> PlatformFileIndexingStatus:
    store = get_store()
    if not hasattr(store, "list_platform_files"):
        return PlatformFileIndexingStatus(updated_at=now_utc())

    files = store.list_platform_files()
    status_by_file_id = _document_status_by_file_id(store)
    all_file_ids = {platform_file.id for platform_file in files}
    linked_file_ids = set(status_by_file_id.keys()).intersection(all_file_ids)

    running_files = {
        file_id for file_id in linked_file_ids if status_by_file_id[file_id] == JobStatus.running
    }
    pending_files = {
        file_id for file_id in linked_file_ids if status_by_file_id[file_id] == JobStatus.pending
    }
    failed_files = {
        file_id for file_id in linked_file_ids if status_by_file_id[file_id] == JobStatus.failed
    }
    completed_files = {
        file_id for file_id in linked_file_ids if status_by_file_id[file_id] == JobStatus.completed
    }
    missing_documents = all_file_ids.difference(linked_file_ids)
    backlog_files = pending_files.union(running_files).union(missing_documents)

    return PlatformFileIndexingStatus(
        total_files=len(files),
        documents_linked=len(linked_file_ids),
        completed_files=len(completed_files),
        pending_files=len(pending_files),
        running_files=len(running_files),
        failed_files=len(failed_files),
        missing_documents=len(missing_documents),
        backlog_files=len(backlog_files),
        indexing_in_background=len(backlog_files) > 0,
        updated_at=now_utc(),
    )


def start_index_worker() -> None:
    global _last_backfill_at, _last_recovery_at
    _ensure_worker_thread()
    recover_pending_platform_file_indexes()
    now = monotonic()
    _last_recovery_at = now
    _last_backfill_at = now
