"""add tag cooccurrences table

Revision ID: 20260421_000002
Revises: 20260421_000001
Create Date: 2026-04-21 00:00:02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260421_000002"
down_revision: str | None = "20260421_000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    if _has_table("tag_cooccurrences"):
        return

    op.create_table(
        "tag_cooccurrences",
        sa.Column("tag_a_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_b_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("tag_a_id", "tag_b_id", name="pk_tag_cooccurrences"),
    )

    op.create_index("ix_tag_cooccurrences_weight", "tag_cooccurrences", ["weight"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tag_cooccurrences_weight", table_name="tag_cooccurrences")
    op.drop_table("tag_cooccurrences")
