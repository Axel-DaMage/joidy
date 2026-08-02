"""add mood_entries table for daily mood tracking

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-02 18:30:00.000000

Mood Tracker widget (#392) — records a daily mood score (1-5) with an
optional note. One entry per user per day enforced by a unique constraint.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mood_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "entry_date", name="uq_mood_entry_user_date"),
    )
    op.create_index(op.f("ix_mood_entries_id"), "mood_entries", ["id"], unique=False)
    op.create_index(op.f("ix_mood_entries_user_id"), "mood_entries", ["user_id"], unique=False)
    op.create_index("ix_mood_entries_entry_date", "mood_entries", ["entry_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mood_entries_entry_date", table_name="mood_entries")
    op.drop_index(op.f("ix_mood_entries_user_id"), table_name="mood_entries")
    op.drop_index(op.f("ix_mood_entries_id"), table_name="mood_entries")
    op.drop_table("mood_entries")
