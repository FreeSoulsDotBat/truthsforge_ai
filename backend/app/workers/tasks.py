from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.contracts import JobStatus, new_id


@dataclass
class WorkerJob:
    kind: str
    payload: dict
    id: str = field(default_factory=lambda: new_id("job"))
    status: JobStatus = JobStatus.pending
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def enqueue_indexing_job(document_id: str) -> WorkerJob:
    return WorkerJob(kind="document.index", payload={"document_id": document_id})
