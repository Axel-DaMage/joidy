"""add_email_messages

Revision ID: e6f7a8b9c0d1
Revises: 3a4b5c6d7e8f
Create Date: 2026-10-26 00:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "3a4b5c6d7e8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account", sa.String(length=255), nullable=False),
        sa.Column("gmail_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("sender", sa.String(length=320), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("important", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("importance_reason", sa.String(length=255), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "account", "gmail_id", name="uq_email_user_account_gmail"),
    )
    op.create_index(op.f("ix_email_messages_id"), "email_messages", ["id"], unique=False)
    op.create_index("ix_email_messages_received_at", "email_messages", ["received_at"], unique=False)
    op.create_index("ix_email_messages_user_id", "email_messages", ["user_id"], unique=False)
    op.create_index("ix_email_messages_user_unread", "email_messages", ["user_id", "unread"], unique=False)
    op.create_index("ix_email_messages_user_important", "email_messages", ["user_id", "important"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_email_messages_user_important", table_name="email_messages")
    op.drop_index("ix_email_messages_user_unread", table_name="email_messages")
    op.drop_index("ix_email_messages_user_id", table_name="email_messages")
    op.drop_index("ix_email_messages_received_at", table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_id"), table_name="email_messages")
    op.drop_table("email_messages")
