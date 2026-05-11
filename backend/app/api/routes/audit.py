from fastapi import APIRouter

from app.core.contracts import AuditEvent
from app.storage.store import get_store

router = APIRouter()


@router.get("/events", response_model=list[AuditEvent])
def list_events() -> list[AuditEvent]:
    return get_store().list_audit_events()
