"""add composite (user_id, received_at DESC NULLS LAST, id DESC) inbox index

Revision ID: e1664f0a1b2c
Revises: c6d7e8f9a0b1
Create Date: 2026-11-21 00:00:00.000000

The unified inbox query filters ``user_id`` and orders by
``received_at DESC NULLS LAST, id DESC``, but the only supporting index
was single-column ``ix_email_messages_received_at`` — every load either
seq-scanned the user's rows or ran an in-memory sort (#1664).

NULLS placement matters: ``received_at`` is nullable and the sort requests
NULLS LAST, while a backward scan of a plain ASC btree yields NULLS FIRST
— the index must declare ``DESC NULLS LAST`` explicitly or Postgres cannot
use it for ordering. ``id`` is appended (DESC) so the full ORDER BY is
satisfied by the index alone (no extra sort step).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1664f0a1b2c"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_email_messages_user_received_at",
        "email_messages",
        [
            sa.text("user_id"),
            sa.text("received_at DESC NULLS LAST"),
            sa.text("id DESC"),
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_messages_user_received_at", table_name="email_messages")
