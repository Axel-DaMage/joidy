"""encrypt secrets and sensitive fields at rest

Revision ID: f8a9b0c1d2e3
Revises: f7a8b9c0d1e2
Create Date: 2026-11-24 12:00:00.000000

Issues #1286 (F-14) and #1329 (D-01) — ISO 27001:2022 Annex A 8.24.

The listed columns are now transparently encrypted by the ``EncryptedText``
SQLAlchemy type (Fernet, key derived from SECRET_KEY exactly like the
existing ``google_tokens.refresh_token_encrypted``). This migration:

1. Widens the bounded ``VARCHAR`` columns to ``TEXT`` so ciphertext fits
   (Fernet output is plaintext + ~100 bytes of envelope, base64'd).
2. Eagerly encrypts every existing plaintext value so a ``pg_dump`` taken
   right after the upgrade shows ciphertext — long-lived secrets like
   ``webhook_secret`` would otherwise stay plaintext until rewritten.

Already-ciphertext values are detected and skipped, making the data pass
idempotent and safe to re-run. ``EncryptedText`` also tolerates residual
plaintext on read as a safety net (lazy migration).
"""

import base64
import hashlib
import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# table -> columns backed by the EncryptedText type. Mirrors the model
# definitions; kept as a literal constant so the migration stays
# self-contained and immune to future model changes.
_ENCRYPTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "google_tokens": ("access_token",),
    "email_messages": ("body_text",),
    "github_repos": ("webhook_secret",),
    "push_subscriptions": ("endpoint", "p256dh", "auth"),
    "google_calendar_events": ("summary", "description", "location"),
    "google_calendar_sync_state": ("sync_token",),
}


def _load_secret_key() -> str:
    """Resolve SECRET_KEY the same way runtime code does.

    Compose injects it as an env var; fall back to config.Settings (which
    also reads the .env file) for bare `alembic upgrade head` invocations.
    """
    secret = os.environ.get("SECRET_KEY")
    if secret:
        return secret
    try:
        from config import settings

        return settings.secret_key or ""
    except Exception:
        return ""


def _fernet() -> Fernet:
    """Same derivation as encryption.get_fernet() — SHA-256 of SECRET_KEY."""
    key = hashlib.sha256(_load_secret_key().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _crypt_existing_rows(*, encrypt: bool) -> None:
    """Rewrite existing values to match the new EncryptedText columns.

    upgrade: encrypt legacy plaintext (skipping anything already ciphertext,
    so re-runs are no-ops). downgrade: decrypt back to plaintext (skipping
    values that are not valid Fernet tokens).
    """
    fernet = _fernet()
    conn = op.get_bind()
    for table, columns in _ENCRYPTED_COLUMNS.items():
        for col in columns:
            rows = conn.execute(sa.text(f"SELECT id, {col} AS v FROM {table} WHERE {col} IS NOT NULL")).mappings().all()
            for row in rows:
                value = row["v"]
                try:
                    fernet.decrypt(value.encode())
                    is_ciphertext = True
                except InvalidToken:
                    is_ciphertext = False
                if encrypt:
                    if is_ciphertext:
                        continue
                    new_value = fernet.encrypt(value.encode()).decode()
                else:
                    if not is_ciphertext:
                        continue
                    new_value = fernet.decrypt(value.encode()).decode()
                conn.execute(
                    sa.text(f"UPDATE {table} SET {col} = :v WHERE id = :row_id"),
                    {"v": new_value, "row_id": row["id"]},
                )


def upgrade() -> None:
    # Widen bounded VARCHAR columns to TEXT before storing ciphertext.
    op.alter_column("github_repos", "webhook_secret", type_=sa.Text())
    for col in ("endpoint", "p256dh", "auth"):
        op.alter_column("push_subscriptions", col, type_=sa.Text())
    _crypt_existing_rows(encrypt=True)


def downgrade() -> None:
    _crypt_existing_rows(encrypt=False)
    for col in ("endpoint", "p256dh", "auth"):
        op.alter_column("push_subscriptions", col, type_=sa.String())
    op.alter_column("github_repos", "webhook_secret", type_=sa.String(length=100))
