"""chats_modeling_fields

Adds JSONB indexes on the new chat-level modeling fields introduced by
ADR-013 (Onda 2.1):

* ``payload->>'is_modeling_3d'`` — used by the sidebar to highlight 3D
  chats with the ``ChatModeling3DBadge``.
* ``payload->>'modeling_stage'`` — used by the chat orchestrator to find
  chats that are mid-flow (``planning``, ``approved``, ``executing``,
  ``editing``).
* ``payload->>'modeling_plan_id'`` — used to look up the primary plan
  attached to a chat without scanning every plan row.

The fields themselves live inside ``payload JSONB`` because chat
sessions store everything in a single JSONB column (ADR-004); this
migration only creates the indexes.

Revision ID: 003_chats_modeling_fields
Revises: 002_chats_title_not_null
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "003_chats_modeling_fields"
down_revision = "002_chats_title_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_modeling_3d
        ON chat_sessions ((payload->>'is_modeling_3d'))
        WHERE payload->>'is_modeling_3d' = 'true'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_modeling_stage
        ON chat_sessions ((payload->>'modeling_stage'))
        WHERE payload->>'modeling_stage' IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_modeling_plan
        ON chat_sessions ((payload->>'modeling_plan_id'))
        WHERE payload->>'modeling_plan_id' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chat_sessions_modeling_plan")
    op.execute("DROP INDEX IF EXISTS idx_chat_sessions_modeling_stage")
    op.execute("DROP INDEX IF EXISTS idx_chat_sessions_modeling_3d")
