"""add integration_tokens

Revision ID: a2b3c4d5e6f7
Revises: f8a9b0c1d2e3
Create Date: 2026-11-20 17:00:00.000000

Issue #44 — provider-agnostic OAuth token storage. One row per ``provider``
(Strava today, Spotify next in #45) holds the access token (encrypted at
rest via the ``EncryptedText`` column type, #1286/#1329) and the refresh
token (Fernet ciphertext written by ``integration_token_service``). No
user data is backfilled — existing Strava "tokens in callback body"
clients re-connect once through the new callback.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(), nullable=False, server_default="Bearer"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("account_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )
    op.create_index(op.f("ix_integration_tokens_id"), "integration_tokens", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_tokens_id"), table_name="integration_tokens")
    op.drop_table("integration_tokens")
