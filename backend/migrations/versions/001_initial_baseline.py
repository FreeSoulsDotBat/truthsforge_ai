"""initial_baseline

Captura o estado atual do schema Postgres produzido por
``PostgresStore.init_schema()`` (ADR-013, Onda 1.4). Todas as DDLs são
idempotentes (``CREATE … IF NOT EXISTS``) para conviver com bancos
existentes sem perder dados.

Revision ID: 001_initial_baseline
Revises:
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "001_initial_baseline"
down_revision = None
branch_labels = None
depends_on = None


_TABLES_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS model_configs (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agents (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prompts (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_folders (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
      id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS platform_files (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_categories (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_bases (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_base_documents (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_jobs (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_sessions (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_plans (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_snapshots (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_tool_calls (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_modeling_tool_calls_plan
    ON modeling_tool_calls ((payload->>'plan_id'))
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_modeling_tool_calls_step
    ON modeling_tool_calls ((payload->>'step_id'))
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_printability_reports (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_modeling_print_reports_plan
    ON modeling_printability_reports ((payload->>'plan_id'))
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_model_versions (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_modeling_versions_project
    ON modeling_model_versions ((payload->>'project_id'))
    """,
    """
    CREATE TABLE IF NOT EXISTS cost_policy (
      id TEXT PRIMARY KEY,
      payload JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
]


def upgrade() -> None:
    for statement in _TABLES_DDL:
        op.execute(statement)


def downgrade() -> None:
    # ``001_initial_baseline`` representa o estado fundamental do banco
    # — descer dele apaga TODAS as tabelas da aplicação. Em ambiente
    # local-first esse cenário pode acontecer durante experimentos com
    # bancos descartáveis, mas em produção o operador deve preferir
    # restaurar de backup. Mantemos o downgrade explícito para que o
    # Alembic não falhe ao tentar regredir.
    for table in [
        "cost_policy",
        "modeling_model_versions",
        "modeling_printability_reports",
        "modeling_tool_calls",
        "modeling_snapshots",
        "modeling_plans",
        "modeling_sessions",
        "import_jobs",
        "audit_events",
        "knowledge_base_documents",
        "knowledge_bases",
        "knowledge_categories",
        "platform_files",
        "documents",
        "chat_messages",
        "chat_sessions",
        "project_folders",
        "projects",
        "prompts",
        "agents",
        "model_configs",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
