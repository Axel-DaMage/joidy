"""add email_accounts + email_messages.account_id (multi-account mail, #1659)

Revision ID: f0e1d2c3b4a5
Revises: c6d7e8f9a0b1
Create Date: 2026-12-02 00:00:00.000000

Introduces the provider-agnostic ``email_accounts`` table — one row per
(user, provider, email_address) with an encrypted credentials blob, an
opaque ``sync_cursor`` (Gmail historyId today; UIDVALIDITY/deltaToken later)
and a per-account ``watch_state`` JSON that replaces the single global
``gmail_watch_state`` system_config key for account-scoped mailboxes.

``email_messages`` gains ``account_id`` FK → email_accounts.id
(ON DELETE SET NULL — disconnecting an account keeps the synced mail).

Data migration, transparent for existing installs:

1. Every DISTINCT ``email_messages.account`` string gets an ``n8n`` provider
   account row and the messages are backfilled onto it — n8n stays a
   first-class ingestion provider.
2. The single ``google_tokens`` row (if present) is copied into a ``gmail``
   account whose ``credentials`` blob re-encrypts the same access/refresh
   tokens. The shared ``google_tokens`` row is left untouched: calendar and
   contacts still use it, and the gmail account now owns an independent
   refresh token. Its real ``email_address`` is unknown inside a migration
   (no network), so the row starts as ``__pending__`` and is resolved via
   ``users.getProfile`` on first use at runtime.
3. The legacy ``gmail_watch_state`` system_config value is moved onto that
   account's ``watch_state``/``sync_cursor`` so the per-account history
   cursor survives.
"""

import base64
import hashlib
import json
import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken

# revision identifiers, used by Alembic.
revision: str = "f0e1d2c3b4a5"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLACEHOLDER_EMAIL = "__pending__"
_WATCH_STATE_KEY = "gmail_watch_state"


def _load_secret_key() -> str:
    """Resolve SECRET_KEY the same way runtime code does — identical to the
    f8a9b0c1d2e3 data migration."""
    secret = os.environ.get("SECRET_KEY")
    if secret:
        return secret
    try:
        from config import settings

        return settings.secret_key or ""
    except Exception:
        return ""


def _fernet() -> Fernet:
    key = hashlib.sha256(_load_secret_key().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _maybe_decrypt(fernet: Fernet, value: str | None) -> str | None:
    """Decrypt a stored EncryptedText/encrypt_str value; legacy plaintext
    rows pass through unchanged (same lazy-migration contract)."""
    if value is None:
        return None
    try:
        return fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return value


def _migrate_n8n_accounts(conn) -> None:
    """One n8n email_accounts row per distinct pushed ``account`` string, then
    backfill email_messages.account_id."""
    accounts = conn.execute(
        sa.text("SELECT DISTINCT user_id, account FROM email_messages ORDER BY user_id, account")
    ).all()
    for user_id, account in accounts:
        address = (account or "")[:320]
        if not address:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO email_accounts "
                "(user_id, provider, email_address, display_name, is_active) "
                "VALUES (:uid, 'n8n', :addr, :name, true)"
            ),
            {"uid": user_id, "addr": address, "name": address},
        )
        row_id = conn.execute(
            sa.text(
                "SELECT id FROM email_accounts WHERE user_id = :uid AND provider = 'n8n' AND email_address = :addr"
            ),
            {"uid": user_id, "addr": address},
        ).scalar()
        conn.execute(
            sa.text(
                "UPDATE email_messages SET account_id = :aid "
                "WHERE user_id = :uid AND account = :addr AND account_id IS NULL"
            ),
            {"aid": row_id, "uid": user_id, "addr": account},
        )


def _migrate_google_token(conn, fernet: Fernet) -> None:
    """Copy the single google_tokens row into a gmail email_accounts row and
    move the legacy gmail_watch_state config onto it."""
    row = (
        conn.execute(
            sa.text(
                "SELECT user_id, access_token, refresh_token_encrypted, token_type, "
                "expires_at, scope FROM google_tokens ORDER BY id LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return

    credentials = {
        "access_token": _maybe_decrypt(fernet, row["access_token"]),
        "refresh_token": _maybe_decrypt(fernet, row["refresh_token_encrypted"]),
        "token_type": row["token_type"] or "Bearer",
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        "scope": row["scope"],
    }
    credentials_json = fernet.encrypt(json.dumps(credentials).encode()).decode()

    # Move the legacy global watch registration onto the new account so its
    # historyId cursor is not lost (#1659 per-account cursors).
    watch_state: dict | None = None
    raw_watch = conn.execute(
        sa.text("SELECT value FROM system_config WHERE key = :k"),
        {"k": _WATCH_STATE_KEY},
    ).scalar()
    sync_cursor = None
    if raw_watch:
        try:
            parsed = json.loads(raw_watch)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and parsed:
            watch_state = parsed
            history_id = parsed.get("history_id")
            sync_cursor = str(history_id) if history_id is not None else None

    stmt = sa.text(
        "INSERT INTO email_accounts "
        "(user_id, provider, email_address, display_name, is_active, "
        " credentials, sync_cursor, watch_state) "
        "VALUES (:uid, 'gmail', :addr, 'Gmail', true, :creds, :cursor, :watch)"
    ).bindparams(sa.bindparam("watch", type_=sa.JSON()))
    conn.execute(
        stmt,
        {
            "uid": row["user_id"],
            "addr": _PLACEHOLDER_EMAIL,
            "creds": credentials_json,
            "cursor": sync_cursor,
            "watch": watch_state,
        },
    )


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=True),
        sa.Column("sync_cursor", sa.String(length=255), nullable=True),
        sa.Column("watch_state", sa.JSON(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", "email_address", name="uq_email_accounts_user_provider_address"),
    )
    op.create_index("ix_email_accounts_id", "email_accounts", ["id"], unique=False)
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"], unique=False)

    op.add_column("email_messages", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index("ix_email_messages_account_id", "email_messages", ["account_id"], unique=False)
    op.create_foreign_key(
        "fk_email_messages_account_id",
        "email_messages",
        "email_accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    conn = op.get_bind()
    _migrate_n8n_accounts(conn)
    # No swallow: if the credential copy fails (e.g. missing SECRET_KEY), the
    # alembic transaction rolls back cleanly instead of leaving a gmail
    # account row without credentials that could never work.
    _migrate_google_token(conn, _fernet())


def downgrade() -> None:
    # email_messages keeps its ``account`` label — no mail data is lost when
    # the accounts table goes away.
    op.drop_constraint("fk_email_messages_account_id", "email_messages", type_="foreignkey")
    op.drop_index("ix_email_messages_account_id", table_name="email_messages")
    op.drop_column("email_messages", "account_id")
    op.drop_index("ix_email_accounts_user_id", table_name="email_accounts")
    op.drop_index("ix_email_accounts_id", table_name="email_accounts")
    op.drop_table("email_accounts")
