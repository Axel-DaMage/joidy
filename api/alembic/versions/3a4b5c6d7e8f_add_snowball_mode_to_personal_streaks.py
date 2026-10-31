"""add_snowball_mode_to_personal_streaks

Revision ID: 3a4b5c6d7e8f
Revises: 256cd4e9a94a
Create Date: 2026-09-13 18:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a4b5c6d7e8f"
down_revision: str | None = "256cd4e9a94a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "personal_streaks", sa.Column("snowball_mode", sa.Boolean(), nullable=False, server_default=sa.text("false"))
    )


def downgrade() -> None:
    op.drop_column("personal_streaks", "snowball_mode")
