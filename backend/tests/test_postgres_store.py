import psycopg
import psycopg_pool
import pytest
from psycopg.rows import dict_row

from app.storage import postgres_store
from app.storage.postgres_store import PostgresStore

_DATABASE_URL = "postgresql://forge:forge@postgres:5432/truths_forge_ai"


def make_store() -> PostgresStore:
    store = PostgresStore.__new__(PostgresStore)
    store.database_url = _DATABASE_URL
    store._pool = None
    return store


class _FakePool:
    """Pool de mentira: `wait()` levanta a exceção pré-programada (ou nada)."""

    def __init__(self, wait_error: Exception | None) -> None:
        self._wait_error = wait_error
        self.closed = False

    def wait(self, timeout: float) -> None:
        if self._wait_error is not None:
            raise self._wait_error

    def close(self) -> None:
        self.closed = True


def _patch_pool_factory(monkeypatch, wait_errors: list[Exception | None]):
    """Faz `psycopg_pool.ConnectionPool(...)` devolver um _FakePool por tentativa,
    cujo `wait()` levanta `wait_errors[i]`. Registra kwargs e pools criados.

    storage-002: o retry de boot agora envolve a ABERTURA do pool (ConnectionPool +
    wait()), não mais um `psycopg.connect` por operação.
    """

    created_kwargs: list[dict] = []
    pools: list[_FakePool] = []
    errors = iter(wait_errors)

    def fake_pool(**kwargs) -> _FakePool:
        created_kwargs.append(kwargs)
        pool = _FakePool(next(errors))
        pools.append(pool)
        return pool

    monkeypatch.setattr(postgres_store.psycopg_pool, "ConnectionPool", fake_pool)
    return created_kwargs, pools


def test_postgres_pool_open_retries_transient_dns_failure(monkeypatch) -> None:
    transient = psycopg.OperationalError(
        "failed to resolve host 'postgres': [Errno -3] Temporary failure in name resolution"
    )
    created, pools = _patch_pool_factory(monkeypatch, [transient, transient, None])
    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(postgres_store, "_POSTGRES_CONNECT_ATTEMPTS", 3)

    pool = make_store()._open_pool()

    assert pool is pools[2]  # 3a tentativa abre com sucesso
    assert len(created) == 3
    assert all(kwargs["conninfo"] == _DATABASE_URL for kwargs in created)
    assert created[0]["kwargs"]["row_factory"] is dict_row
    assert pools[0].closed and pools[1].closed  # pools que falharam são fechados
    assert not pools[2].closed
    assert sleeps == [postgres_store._POSTGRES_CONNECT_RETRY_DELAY_SECONDS] * 2


def test_postgres_pool_open_raises_after_retry_budget(monkeypatch) -> None:
    refused = psycopg.OperationalError("connection refused")
    created, pools = _patch_pool_factory(monkeypatch, [refused, refused])
    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(postgres_store, "_POSTGRES_CONNECT_ATTEMPTS", 2)

    with pytest.raises(psycopg.OperationalError, match="connection refused"):
        make_store()._open_pool()

    assert len(created) == 2
    assert all(pool.closed for pool in pools)
    assert sleeps == [postgres_store._POSTGRES_CONNECT_RETRY_DELAY_SECONDS]


def test_postgres_pool_open_does_not_retry_authentication_failure(monkeypatch) -> None:
    auth = psycopg.OperationalError("password authentication failed for user forge")
    created, pools = _patch_pool_factory(monkeypatch, [auth])
    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(psycopg.OperationalError, match="password authentication failed"):
        make_store()._open_pool()

    assert len(created) == 1  # erro não-retryável: falha na 1a tentativa
    assert pools[0].closed
    assert sleeps == []


def test_postgres_pool_open_passes_health_check_and_configurable_max_size(monkeypatch) -> None:
    # Pós-restart do Postgres o pool pode reter conexões mortas; o ``check``
    # de checkout as descarta em vez de entregá-las (OperationalError em série).
    created, pools = _patch_pool_factory(monkeypatch, [None])
    monkeypatch.setattr(postgres_store.settings, "postgres_pool_max_size", 7)

    pool = make_store()._open_pool()

    assert pool is pools[0]
    kwargs = created[0]
    # Referência capturada no import — sobrevive ao monkeypatch da factory
    # (dentro do teste, psycopg_pool.ConnectionPool já é o fake, sem o método).
    assert kwargs["check"] is postgres_store._POSTGRES_POOL_CHECK
    assert kwargs["max_size"] == 7  # configurável via Settings/env
    assert kwargs["min_size"] == postgres_store._POSTGRES_POOL_MIN_SIZE


def test_postgres_pool_max_size_floor_protects_nested_checkouts(monkeypatch) -> None:
    # max_size=1 deadlocka em checkouts aninhados na mesma thread (um método
    # segura uma conexão e chama outro que faz novo checkout) — piso 2.
    created, _ = _patch_pool_factory(monkeypatch, [None])
    monkeypatch.setattr(postgres_store.settings, "postgres_pool_max_size", 1)

    make_store()._open_pool()

    assert created[0]["max_size"] == postgres_store._POSTGRES_POOL_MAX_SIZE_FLOOR


def test_postgres_pool_open_retries_pool_timeout(monkeypatch) -> None:
    # PoolTimeout durante a janela de boot é sempre retryável (storage-002).
    created, pools = _patch_pool_factory(
        monkeypatch, [psycopg_pool.PoolTimeout("pool open timed out"), None]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(postgres_store, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(postgres_store, "_POSTGRES_CONNECT_ATTEMPTS", 3)

    pool = make_store()._open_pool()

    assert pool is pools[1]
    assert len(created) == 2
    assert pools[0].closed and not pools[1].closed
    assert sleeps == [postgres_store._POSTGRES_CONNECT_RETRY_DELAY_SECONDS]


def test_get_max_trace_sequence_uses_aggregate_query(monkeypatch) -> None:
    store = make_store()

    class Cursor:
        def __init__(self) -> None:
            self.sql = ""
            self.params: tuple[object, ...] | None = None

        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, sql: str, params: tuple[object, ...]) -> None:
            self.sql = sql
            self.params = params

        def fetchone(self) -> dict[str, int]:
            return {"max_sequence": 12}

    class Connection:
        def __init__(self, cursor: Cursor) -> None:
            self._cursor = cursor

        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return self._cursor

    cursor = Cursor()
    monkeypatch.setattr(store, "_connect", lambda: Connection(cursor))

    assert store.get_max_trace_sequence(trace_id="mt_test_trace") == 12
    assert "MAX((payload->>'sequence')::int)" in cursor.sql
    assert "WHERE trace_id = %s" in cursor.sql
    assert cursor.params == ("mt_test_trace",)
