"""add goal context and inbox state

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-11-19 00:00:00.000000

Adds GoalContext enum (ANY, MORNING, NIGHT), adds INBOX to GoalState,
and adds context column to goals table (#1198).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTEXT_VALUES = ["ANY", "MORNING", "NIGHT"]


def upgrade() -> None:
    # 1. Add INBOX value to existing goalstate enum in PostgreSQL
    # ALTER TYPE ADD VALUE cannot run inside an ongoing transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE goalstate ADD VALUE IF NOT EXISTS 'INBOX'")

    # 2. Create goalcontext enum type if not exists
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE goalcontext AS ENUM ('ANY', 'MORNING', 'NIGHT');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    context_enum = ENUM(*CONTEXT_VALUES, name="goalcontext", create_type=False)

    # 3. Add column context to goals table
    op.add_column(
        "goals",
        sa.Column(
            "context",
            context_enum,
            nullable=False,
            server_default="ANY",
        ),
    )
    op.create_index("ix_goals_context", "goals", ["context"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_goals_context", table_name="goals")
    op.drop_column("goals", "context")
    op.execute("DROP TYPE IF EXISTS goalcontext")
    # Note: PostgreSQL does not support removing values from an ENUM (INBOX remains in goalstate safely).
