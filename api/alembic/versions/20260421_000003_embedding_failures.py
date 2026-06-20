"""add embedding failures dlq

Revision ID: 20260421_000003
Revises: 20260421_000002
Create Date: 2026-04-21 00:00:03
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260421_000003"
down_revision: str | None = "20260421_000002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    if _has_table("embedding_failures"):
        return

    op.create_table(
        "embedding_failures",
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("note_id", name="pk_embedding_failures"),
    )

    op.create_index("ix_embedding_failures_next_retry_at", "embedding_failures", ["next_retry_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_embedding_failures_next_retry_at", table_name="embedding_failures")
    op.drop_table("embedding_failures")
