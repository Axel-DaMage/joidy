"""add_oneoff_to_temporality

Revision ID: d9a0fdaa6f90
Revises: a7b8c9d0e1f2
Create Date: 2026-08-30 02:16:57.147789
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9a0fdaa6f90"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE goaltemporality ADD VALUE 'ONEOFF'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing values from enum types,
    # so we just pass.
    pass
