from __future__ import annotations

from queue import Empty, Queue
from threading import Lock, Thread

from app.core.contracts import JobStatus
from app.importers.chatgpt_jobs import process_chatgpt_import_job
from app.storage.store import get_store

_queue: Queue[str] = Queue()
_thread_lock = Lock()
_enqueued_ids: set[str] = set()
_worker_thread: Thread | None = None


def _worker_loop() -> None:
    while True:
        try:
            job_id = _queue.get(timeout=0.5)
        except Empty:
            continue
        try:
            process_chatgpt_import_job(job_id)
        finally:
            with _thread_lock:
                _enqueued_ids.discard(job_id)
            _queue.task_done()


def _ensure_worker_thread() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    with _thread_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_thread = Thread(
            target=_worker_loop,
            name="truths-forge-chatgpt-importer",
            daemon=True,
        )
        _worker_thread.start()


def enqueue_chatgpt_import_job(job_id: str | None) -> None:
    if not job_id:
        return
    _ensure_worker_thread()
    with _thread_lock:
        if job_id in _enqueued_ids:
            return
        _enqueued_ids.add(job_id)
    _queue.put(job_id)


def recover_pending_import_jobs() -> None:
    store = get_store()
    if not hasattr(store, "list_import_jobs"):
        return
    jobs = store.list_import_jobs()
    for job in jobs:
        if job.status not in {JobStatus.pending, JobStatus.running}:
            continue
        if job.status == JobStatus.running:
            job.status = JobStatus.pending
            job.current_step = "Retomando após reinício do backend"
            if hasattr(store, "upsert_import_job"):
                store.upsert_import_job(job)
        enqueue_chatgpt_import_job(job.id)


def start_import_worker() -> None:
    _ensure_worker_thread()
    recover_pending_import_jobs()
