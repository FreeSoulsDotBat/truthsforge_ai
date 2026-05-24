from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.storage.dev_store import get_dev_store

logger = logging.getLogger(__name__)

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
            # DT-007: backend "auto" com Postgres indisponível. NÃO cai em JSON
            # silenciosamente — registra o motivo. A degradação é persistente
            # (o _store fica cacheado no módulo até reiniciar), então o operador
            # precisa saber que está rodando no dev-store JSON (apenas dev/test,
            # P5). Para falhar em vez de degradar, use
            # TRUTHS_FORGE_STORAGE_BACKEND=postgres.
            logger.warning(
                "storage_backend='auto': Postgres indisponível; degradando para "
                "o dev-store JSON (apenas dev/test, P5).",
                exc_info=True,
            )

    _store = get_dev_store()
    return _store
