from fastapi import APIRouter

from app.core.contracts import AuditEvent
from app.storage.store import get_store

router = APIRouter()

MAX_AUDIT_EVENTS = 200


@router.get("/events", response_model=list[AuditEvent])
def list_events(limit: int = 200, offset: int = 0) -> list[AuditEvent]:
    # Eventos crescem sem limite; capa o slice para evitar respostas gigantes.
    normalized_limit = max(1, min(int(limit), MAX_AUDIT_EVENTS))
    normalized_offset = max(0, int(offset))
    events = get_store().list_audit_events()
    return events[normalized_offset : normalized_offset + normalized_limit]
