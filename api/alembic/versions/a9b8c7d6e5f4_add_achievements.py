"""add achievements table for persistent gamification unlocks

Revision ID: a9b8c7d6e5f4
Revises: e6f7a8b9c0d1
Create Date: 2026-10-30 10:00:00.000000

Issue #1137 — achievements move from frontend localStorage to PostgreSQL.
One row per unlocked achievement, idempotent per (user_id, achievement_key).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("achievement_key", sa.String(length=100), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "achievement_key", name="uq_achievements_user_key"),
    )
    op.create_index(op.f("ix_achievements_id"), "achievements", ["id"], unique=False)
    op.create_index(op.f("ix_achievements_user_id"), "achievements", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_achievements_user_id"), table_name="achievements")
    op.drop_index(op.f("ix_achievements_id"), table_name="achievements")
    op.drop_table("achievements")
