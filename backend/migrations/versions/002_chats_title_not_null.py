"""chats_title_not_null

Backfill the ``title`` field of every existing ``chat_sessions`` row that
is missing a title or carries an empty/whitespace title (ADR-014). The
title itself lives inside ``payload JSONB``, so this migration is a
``UPDATE`` against the JSONB tree rather than a column constraint change.

The chosen default uses ``created_at`` from the payload so the operator
can still skim a list and figure out roughly when each unnamed chat was
created.

After this migration runs, the application enforces non-empty titles via
``ChatSessionCreate`` (Pydantic validator) and the ``POST /api/chat/stream``
422 check (Onda 2.9). A subsequent migration could promote ``title`` to a
top-level ``NOT NULL`` column once the project moves off JSONB-only
storage.

Revision ID: 002_chats_title_not_null
Revises: 001_initial_baseline
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "002_chats_title_not_null"
down_revision = "001_initial_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Two-step backfill so the second statement only touches rows that
    # still have a blank/whitespace title after the first one filled in
    # the structurally missing ones.
    op.execute(
        """
        UPDATE chat_sessions
           SET payload = jsonb_set(
               payload,
               '{title}',
               to_jsonb(
                   'Sem título - ' ||
                   COALESCE(
                       substring(payload->>'created_at' from 1 for 10),
                       to_char(updated_at, 'YYYY-MM-DD')
                   )
               )
           )
         WHERE payload->'title' IS NULL
        """
    )
    op.execute(
        """
        UPDATE chat_sessions
           SET payload = jsonb_set(
               payload,
               '{title}',
               to_jsonb(
                   'Sem título - ' ||
                   COALESCE(
                       substring(payload->>'created_at' from 1 for 10),
                       to_char(updated_at, 'YYYY-MM-DD')
                   )
               )
           )
         WHERE btrim(coalesce(payload->>'title', '')) = ''
        """
    )


def downgrade() -> None:
    # Downgrade is a no-op: we cannot tell which titles were backfilled
    # from which existed before. The original blank titles were never
    # backed up because they didn't carry any information to preserve.
    pass
