from fastapi import APIRouter

from app.core.config import settings
from app.core.contracts import ServerStatus

router = APIRouter()


@router.get("/status", response_model=ServerStatus)
def status() -> ServerStatus:
    return ServerStatus(
        environment=settings.app_env,
        public_base_url=settings.public_base_url,
        features={
            "chat_streaming": True,
            "model_registry": True,
            "judite_dev_provider": True,
            "agents_scaffold": True,
            "rag_scaffold": True,
            "qdrant_vector_store": True,
            "mobile_cache_mode": False,
            "tauri_packaging": False,
            "capacitor_packaging": False,
        },
    )
