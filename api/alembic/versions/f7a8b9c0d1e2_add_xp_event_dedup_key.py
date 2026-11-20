"""add dedup_key to xp_events for idempotent XP awards

Revision ID: f7a8b9c0d1e2
Revises: f5a6b7c8d9e0
Create Date: 2026-11-24 10:00:00.000000

Issue #1320 (B-04) — XP/achievement farming. ``xp_events.dedup_key`` is a
callers-supplied idempotency key; a partial unique index on
``(event_type, dedup_key)`` (rows with NULL dedup_key are exempt) makes
double-awards impossible even under retries/races.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("xp_events", sa.Column("dedup_key", sa.String(length=200), nullable=True))
    op.create_index(
        "uq_xp_events_type_dedup",
        "xp_events",
        ["event_type", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("dedup_key IS NOT NULL"),
        sqlite_where=sa.text("dedup_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_xp_events_type_dedup", table_name="xp_events")
    op.drop_column("xp_events", "dedup_key")
