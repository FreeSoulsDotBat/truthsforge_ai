"""DT-007: o backend de storage ``auto`` não pode cair em JSON silenciosamente.

Quando ``storage_backend == "auto"`` e o Postgres está indisponível, o
``get_store`` degrada para o dev-store JSON (P5: só dev/test) — mas deve
**registrar** a degradação (era um swallow silencioso). No modo ``postgres``
estrito, a falha re-levanta.

Injeta um módulo ``app.storage.postgres_store`` falso via ``sys.modules`` para
forçar a falha de forma determinística, sem depender de ``psycopg`` estar
instalado no ambiente de teste.
"""

from __future__ import annotations

import logging
import sys
import types

import pytest

import app.storage.store as store_module


def _install_failing_postgres(monkeypatch) -> None:
    fake = types.ModuleType("app.storage.postgres_store")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("postgres indisponível (teste)")

    fake.PostgresStore = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.storage.postgres_store", fake)


@pytest.fixture(autouse=True)
def _reset_store_singleton():
    store_module._store = None
    yield
    store_module._store = None


def test_auto_backend_logs_when_falling_back_to_json(monkeypatch, caplog):
    monkeypatch.setattr(store_module.settings, "storage_backend", "auto")
    _install_failing_postgres(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="app.storage.store"):
        store = store_module.get_store()

    assert store is not None  # degradou para o dev-store JSON
    assert any(
        "degradando para o dev-store JSON" in record.getMessage() for record in caplog.records
    ), "a degradação auto→JSON deve ser registrada (DT-007), não silenciosa"


def test_postgres_backend_reraises_instead_of_degrading(monkeypatch):
    monkeypatch.setattr(store_module.settings, "storage_backend", "postgres")
    _install_failing_postgres(monkeypatch)

    with pytest.raises(RuntimeError):
        store_module.get_store()
