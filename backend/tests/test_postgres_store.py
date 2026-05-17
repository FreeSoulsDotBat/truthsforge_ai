import psycopg
import pytest
from psycopg.rows import dict_row

from app.storage import postgres_store
from app.storage.postgres_store import PostgresStore


def make_store() -> PostgresStore:
    store = PostgresStore.__new__(PostgresStore)
    store.database_url = "postgresql://forge:forge@postgres:5432/truths_forge_ai"
    return store


def test_postgres_connect_retries_transient_dns_failure(monkeypatch) -> None:
    attempts: list[tuple[str, object]] = []
    connection = object()

    def fake_connect(database_url: str, row_factory: object) -> object:
        attempts.append((database_url, row_factory))
        if len(attempts) < 3:
            raise psycopg.OperationalError(
                "failed to resolve host 'postgres': [Errno -3] Temporary failure in name resolution"
            )
        return connection

    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store.psycopg, "connect", fake_connect)
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(postgres_store, "_POSTGRES_CONNECT_ATTEMPTS", 3)

    assert make_store()._connect() is connection
    assert attempts == [
        ("postgresql://forge:forge@postgres:5432/truths_forge_ai", dict_row),
        ("postgresql://forge:forge@postgres:5432/truths_forge_ai", dict_row),
        ("postgresql://forge:forge@postgres:5432/truths_forge_ai", dict_row),
    ]
    assert sleeps == [postgres_store._POSTGRES_CONNECT_RETRY_DELAY_SECONDS] * 2


def test_postgres_connect_raises_after_retry_budget(monkeypatch) -> None:
    attempts: list[str] = []

    def fake_connect(database_url: str, row_factory: object) -> object:
        attempts.append(database_url)
        raise psycopg.OperationalError("connection refused")

    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store.psycopg, "connect", fake_connect)
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(postgres_store, "_POSTGRES_CONNECT_ATTEMPTS", 2)

    with pytest.raises(psycopg.OperationalError, match="connection refused"):
        make_store()._connect()

    assert attempts == [
        "postgresql://forge:forge@postgres:5432/truths_forge_ai",
        "postgresql://forge:forge@postgres:5432/truths_forge_ai",
    ]
    assert sleeps == [postgres_store._POSTGRES_CONNECT_RETRY_DELAY_SECONDS]


def test_postgres_connect_does_not_retry_authentication_failure(monkeypatch) -> None:
    attempts: list[str] = []

    def fake_connect(database_url: str, row_factory: object) -> object:
        attempts.append(database_url)
        raise psycopg.OperationalError("password authentication failed for user forge")

    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store.psycopg, "connect", fake_connect)
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(psycopg.OperationalError, match="password authentication failed"):
        make_store()._connect()

    assert attempts == ["postgresql://forge:forge@postgres:5432/truths_forge_ai"]
    assert sleeps == []
