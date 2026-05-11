from __future__ import annotations

from app.core.contracts import AuditEvent
from app.storage.store import get_store


def record_audit_event(event: AuditEvent) -> AuditEvent:
    return get_store().add_audit_event(event)
