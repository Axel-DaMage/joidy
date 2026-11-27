from datetime import datetime

from database import Base
from encryption import EncryptedText
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

# Provider identifiers stored in ``email_accounts.provider``. New providers
# (Outlook via Microsoft Graph, generic IMAP) register here and implement the
# ``EmailProvider`` contract in ``services/email_providers/`` — the schema is
# intentionally provider-agnostic so no migration is needed to add one.
PROVIDER_GMAIL = "gmail"
PROVIDER_N8N = "n8n"
PROVIDER_OUTLOOK = "outlook"
PROVIDER_IMAP = "imap"

KNOWN_PROVIDERS = frozenset({PROVIDER_GMAIL, PROVIDER_N8N, PROVIDER_OUTLOOK, PROVIDER_IMAP})

# Sentinel ``email_address`` for the Gmail account created by the migration
# from the legacy single ``google_tokens`` row — the real address is resolved
# lazily via ``users.getProfile`` the first time the account is used, because
# migrations cannot make network calls.
PLACEHOLDER_EMAIL = "__pending__"


class EmailAccount(Base):
    """A connected mailbox/provider account feeding the unified inbox.

    One row per (user, provider, email_address). ``credentials`` is an
    encrypted JSON blob whose shape is defined by the provider:

    - ``gmail``: ``{access_token, refresh_token, expires_at, scope, token_type}``
      (per-account OAuth grant; refresh tokens are provider-issued and
      independent, so several Gmail mailboxes coexist).
    - ``n8n``: empty — n8n is a push ingestion channel, not a credentialled
      provider; its rows exist so ``email_messages.account_id`` always has a
      referent and pushed mail shows up as a first-class account.
    - ``outlook``/``imap``: reserved — OAuth blob / host+login settings land
      here with no schema change.

    ``sync_cursor`` is the provider's opaque incremental-sync position
    (Gmail historyId today; IMAP UIDVALIDITY/UID or Graph deltaToken later).
    ``watch_state`` keeps the provider's push-subscription record (Gmail
    users.watch: topic/expiration/registered_at) so each mailbox renews and
    polls independently — it replaces the single global ``gmail_watch_state``
    system_config key for account-scoped mailboxes.
    """

    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Encrypted JSON credential blob — never serialize it out of the API.
    credentials: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    # Opaque provider cursor: Gmail historyId today.
    sync_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Provider push/subscription state (Gmail users.watch record).
    watch_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "email_address", name="uq_email_accounts_user_provider_address"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EmailAccount {self.provider}:{self.email_address}>"
