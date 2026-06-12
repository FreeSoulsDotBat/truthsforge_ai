"""Teste de paridade de superfície entre os stores (ADR-015, spec 070).

Garante que ``PostgresStore`` e ``DevStore`` exponham o mesmo conjunto de
métodos públicos de domínio. Evita a divergência silenciosa descrita na
dívida DT-001/DT-003 da spec ``070-storage-persistence``: quando uma
assinatura/método muda em apenas um dos stores.

Métodos exclusivos do Postgres (bootstrap/manutenção sem equivalente no
fallback JSON) ficam em uma allowlist explícita; adicionar um novo método de
domínio em apenas um store quebra este teste de propósito.
"""

from __future__ import annotations

from app.storage.dev_store import DevStore
from app.storage.postgres_store import PostgresStore

# Métodos só do Postgres: bootstrap/manutenção sem equivalente no fallback JSON.
POSTGRES_ONLY = {
    "audit_events_for_month",
    "close",  # storage-002: fecha o connection pool; DevStore não tem recurso a fechar.
    "init_schema",
    "migrate_projects_and_folders",
    "reconcile_chatgpt_session_timestamps",
    "seed_if_empty",
}


def _public_methods(cls: type) -> set[str]:
    return {name for name in dir(cls) if not name.startswith("_") and callable(getattr(cls, name))}


def test_store_surface_parity() -> None:
    postgres = _public_methods(PostgresStore)
    dev = _public_methods(DevStore)

    dev_only = dev - postgres
    assert dev_only == set(), (
        f"Métodos só no DevStore (ausentes no PostgresStore): {sorted(dev_only)}"
    )

    postgres_only = postgres - dev
    assert postgres_only == POSTGRES_ONLY, (
        "Divergência de superfície entre os stores. "
        f"Inesperado só no Postgres: {sorted(postgres_only - POSTGRES_ONLY)}; "
        f"Allowlist sem correspondência atual: {sorted(POSTGRES_ONLY - postgres_only)}"
    )
