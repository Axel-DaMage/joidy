"""add priority column to goals

Revision ID: 9f3e2d1c4b5a
Revises: e6f7a8b9c0d1
Create Date: 2026-10-30 21:30:00.000000

Goal priority for ordering (#1097): higher number = higher priority,
0 = no explicit priority. Existing goals backfill to 0 so the relative
order (created_at desc) is preserved.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f3e2d1c4b5a"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("goals", "priority")
