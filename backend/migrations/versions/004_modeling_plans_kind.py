"""modeling_plans_kind

Cria índices em ``modeling_plans`` para os campos ``kind`` e
``parent_plan_id`` introduzidos pelo ADR-013 (Onda 1.2). Como o payload do
plano vive em ``JSONB``, o campo em si fica disponível sem mudança de
schema; estes índices aceleram queries do tipo "todos os mini-planos de
edição do plano X" usadas pela orquestração chat-first.

Revision ID: 004_modeling_plans_kind
Revises: 001_initial_baseline
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "004_modeling_plans_kind"
down_revision = "001_initial_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_modeling_plans_kind
        ON modeling_plans ((payload->>'kind'))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_modeling_plans_parent
        ON modeling_plans ((payload->>'parent_plan_id'))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_modeling_plans_parent")
    op.execute("DROP INDEX IF EXISTS idx_modeling_plans_kind")
