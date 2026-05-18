"""Alembic environment for the Truth's Forge backend.

The Truth's Forge MVP stores typed payloads as ``JSONB`` instead of fully
normalised columns (see ADR-004), so Alembic operates in "imperative" mode
here: we do **not** declare a SQLAlchemy ``Base.metadata`` to autogenerate
from. Each revision is hand-written with raw ``op.execute()`` / DDL
helpers, mirroring the statements that previously lived in
``PostgresStore.init_schema()``.

Database URL resolution:

1. If ``-x url=...`` is passed on the command line, that wins.
2. Otherwise we read ``app.core.config.settings.database_url``.

Both paths fall back to the dev default so a contributor can run
``alembic upgrade head`` against a local Postgres without exporting any
env vars.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

logger = logging.getLogger("alembic.env")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_database_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if "url" in x_args and x_args["url"]:
        return x_args["url"]
    return settings.database_url


config.set_main_option("sqlalchemy.url", _resolve_database_url())


# ``target_metadata`` stays ``None`` on purpose: we manage schema with
# explicit DDL inside each revision rather than autogenerating from
# SQLAlchemy models.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit SQL scripts without connecting to a live database."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live ``settings.database_url`` connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
