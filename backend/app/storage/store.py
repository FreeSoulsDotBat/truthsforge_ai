from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.storage.dev_store import get_dev_store

_store: Any | None = None


def get_store() -> Any:
    global _store
    if _store is not None:
        return _store

    if settings.storage_backend == "json":
        _store = get_dev_store()
        return _store

    if settings.storage_backend in {"postgres", "auto"}:
        try:
            from app.storage.postgres_store import PostgresStore

            _store = PostgresStore()
            return _store
        except Exception:
            if settings.storage_backend == "postgres":
                raise

    _store = get_dev_store()
    return _store
