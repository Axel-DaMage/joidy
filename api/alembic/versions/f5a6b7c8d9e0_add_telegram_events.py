"""add telegram_events table

Revision ID: f5a6b7c8d9e0
Revises: f4a5b6c7d8e9
Create Date: 2026-12-02 12:00:00.000000

Telegram bot quick-capture integration (#1132). Persists one row per
incoming webhook update (commands such as /note, /goal, /checkin, /ask
and /status, plus plain messages) for auditing, debugging and webhook
retry de-duplication via ``update_id``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("command", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("message_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="received"),
        sa.Column("response", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telegram_events_id"), "telegram_events", ["id"], unique=False)
    op.create_index(op.f("ix_telegram_events_update_id"), "telegram_events", ["update_id"], unique=False)
    op.create_index("ix_telegram_events_status_created", "telegram_events", ["status", "created_at"], unique=False)
    op.create_index("ix_telegram_events_command", "telegram_events", ["command"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_telegram_events_command", table_name="telegram_events")
    op.drop_index("ix_telegram_events_status_created", table_name="telegram_events")
    op.drop_index(op.f("ix_telegram_events_update_id"), table_name="telegram_events")
    op.drop_index(op.f("ix_telegram_events_id"), table_name="telegram_events")
    op.drop_table("telegram_events")
