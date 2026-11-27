"""Email account service (#1659).

CRUD + credential handling for ``email_accounts`` — one row per connected
mailbox/provider account. Credentials are provider-defined JSON blobs in the
``EncryptedText`` column (Gmail: ``{access_token, refresh_token, expires_at,
scope, token_type}``); they never leave the backend.

Gmail specifics live behind small helpers: ``store_gmail_tokens`` upserts an
account after the OAuth callback (``/integrations/gmail/accounts/callback``),
``get_account_access_token`` returns a live access token refreshing and
persisting back into the blob when expired, and ``resolve_pending_profile``
lazily fills the ``__pending__`` placeholder address left by the alembic
migration via ``users.getProfile``.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from models.email_account import (
    PLACEHOLDER_EMAIL,
    PROVIDER_GMAIL,
    PROVIDER_N8N,
    EmailAccount,
)
from models.email_message import EmailMessage
from services import gmail_service as gms
from services import google_service as gs
from services import google_token_service as gts
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_EXPIRY_BUFFER_SECONDS = 60


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_accounts(db: Session, user_id: int, *, provider: str | None = None) -> list[EmailAccount]:
    """All email accounts for the user, newest last — optionally filtered by
    provider."""
    query = db.query(EmailAccount).filter(EmailAccount.user_id == user_id)
    if provider:
        query = query.filter(EmailAccount.provider == provider)
    return query.order_by(EmailAccount.provider, EmailAccount.email_address, EmailAccount.id).all()


def get_account(db: Session, user_id: int, account_id: int) -> EmailAccount | None:
    return db.query(EmailAccount).filter(EmailAccount.user_id == user_id, EmailAccount.id == account_id).first()


def get_account_by_address(db: Session, user_id: int, provider: str, email_address: str) -> EmailAccount | None:
    return (
        db.query(EmailAccount)
        .filter(
            EmailAccount.user_id == user_id,
            EmailAccount.provider == provider,
            EmailAccount.email_address == email_address,
        )
        .first()
    )


def get_or_create_account(
    db: Session,
    user_id: int,
    provider: str,
    email_address: str,
    display_name: str | None = None,
) -> EmailAccount:
    """Idempotent upsert keyed by the (user, provider, address) unique row."""
    existing = get_account_by_address(db, user_id, provider, email_address)
    if existing is not None:
        return existing
    account = EmailAccount(
        user_id=user_id,
        provider=provider,
        email_address=email_address[:320],
        display_name=display_name,
        is_active=True,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        # Lost a create race — re-read the winner.
        db.rollback()
        existing = get_account_by_address(db, user_id, provider, email_address)
        if existing is None:
            raise
        return existing
    db.refresh(account)
    return account


def resolve_message_account(db: Session, user_id: int, account_str: str) -> EmailAccount:
    """Pick the ``email_accounts`` row an ingested message belongs to.

    A pushed ``account`` string matching a credentialled mailbox (e.g. the
    gmail account for ``me@gmail.com``) links the message to that account so
    n8n-pushed and API-synced mail for one mailbox share a single chip.
    Otherwise an ``n8n`` provider row is get-or-created — ingestion keeps
    working with zero account setup.
    """
    for account in list_accounts(db, user_id):
        if account.provider != PROVIDER_N8N and account.email_address == account_str:
            return account
    return get_or_create_account(db, user_id, PROVIDER_N8N, account_str, display_name=account_str)


def update_account(
    db: Session,
    account: EmailAccount,
    *,
    display_name: str | None = None,
    is_active: bool | None = None,
) -> EmailAccount:
    if display_name is not None:
        account.display_name = display_name
    if is_active is not None:
        account.is_active = is_active
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account: EmailAccount) -> None:
    """Disconnect: drops the row (and its credentials) — synced messages keep
    their ``account`` label with ``account_id`` SET NULL."""
    db.delete(account)
    db.commit()


# ---------------------------------------------------------------------------
# Credentials (EncryptedText JSON blob — never serialized out of the API)
# ---------------------------------------------------------------------------


def _load_credentials(account: EmailAccount) -> dict[str, Any]:
    if not account.credentials:
        return {}
    try:
        data = json.loads(account.credentials)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_credentials(db: Session, account: EmailAccount, credentials: dict[str, Any]) -> None:
    account.credentials = json.dumps(credentials)
    db.commit()


async def store_gmail_tokens(
    db: Session,
    user_id: int,
    email_address: str,
    tokens: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
) -> EmailAccount:
    """Upsert a gmail account from an OAuth token response.

    ``tokens`` is the Google token endpoint JSON (access_token, refresh_token,
    expires_in, scope, token_type). An existing row keeps its refresh token
    when the re-consent did not issue a new one; ``profile`` (users.getProfile)
    seeds email/historyId when available.

    A migrated ``__pending__`` placeholder is the same mailbox as the migrated
    shared token — but its real address is only knowable through ITS OWN
    credentials, so it is resolved first: only a placeholder that resolves to
    the connecting address may be reused. Otherwise a different second mailbox
    would hijack the migrated row and its credentials (#1659).
    """
    account = get_account_by_address(db, user_id, PROVIDER_GMAIL, email_address)
    if account is None:
        placeholder = get_account_by_address(db, user_id, PROVIDER_GMAIL, PLACEHOLDER_EMAIL)
        if placeholder is not None and email_address != PLACEHOLDER_EMAIL:
            if await resolve_pending_profile(db, placeholder):
                # Placeholder merged into an existing row or now carries its
                # real address — re-check whether it is the connecting mailbox.
                account = get_account_by_address(db, user_id, PROVIDER_GMAIL, email_address)
    if account is None:
        account = EmailAccount(
            user_id=user_id,
            provider=PROVIDER_GMAIL,
            email_address=email_address[:320],
            display_name=email_address,
            is_active=True,
        )
        db.add(account)

    credentials = _load_credentials(account)
    credentials["access_token"] = tokens.get("access_token")
    if tokens.get("refresh_token"):
        credentials["refresh_token"] = tokens["refresh_token"]
    credentials["token_type"] = tokens.get("token_type") or "Bearer"
    expires_in = int(tokens.get("expires_in") or 3600)
    credentials["expires_at"] = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()
    if tokens.get("scope"):
        credentials["scope"] = tokens["scope"]
    account.credentials = json.dumps(credentials)

    if profile:
        history_id = profile.get("historyId")
        if history_id is not None and not account.sync_cursor:
            account.sync_cursor = str(history_id)
    db.commit()
    db.refresh(account)
    return account


async def get_account_access_token(db: Session, account: EmailAccount) -> str | None:
    """Live access token for a gmail account — refreshes via the account's own
    refresh token and persists the renewed pair back into the blob.

    Returns None when the account has no usable credentials (needs re-auth).
    """
    if account.provider != PROVIDER_GMAIL:
        return None
    credentials = _load_credentials(account)
    access = credentials.get("access_token")
    raw_expiry = credentials.get("expires_at")
    if access and raw_expiry:
        try:
            expires_at = datetime.fromisoformat(str(raw_expiry))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) < expires_at - timedelta(seconds=_EXPIRY_BUFFER_SECONDS):
                return str(access)
        except ValueError:
            pass

    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        return None
    data = await gts.refresh_access_token(str(refresh_token))
    if not data or not data.get("access_token"):
        return None
    credentials["access_token"] = data["access_token"]
    expires_in = int(data.get("expires_in") or 3600)
    credentials["expires_at"] = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()
    _save_credentials(db, account, credentials)
    return str(data["access_token"])


# ---------------------------------------------------------------------------
# Capabilities / profile
# ---------------------------------------------------------------------------


def account_capabilities(account: EmailAccount) -> dict[str, bool | None]:
    """Gmail capability flags read from the account's stored scope string."""
    if account.provider != PROVIDER_GMAIL:
        return {"read": None, "modify": None, "send": None}
    return gms.capabilities_for_scope(_load_credentials(account).get("scope"))


def require_account_capability(account: EmailAccount, capability: str) -> None:
    """Account-scoped variant of ``gmail_service.require_capability``."""
    gms.require_scope_capability(_load_credentials(account).get("scope"), capability)


async def resolve_pending_profile(db: Session, account: EmailAccount) -> bool:
    """Fill a ``__pending__`` email address from users.getProfile.

    The alembic migration cannot call Google, so the migrated gmail row
    carries the placeholder until its first use. On success the address is
    written, ``sync_cursor`` is seeded from the profile historyId, and mail
    previously pushed under that address (n8n) is re-linked onto this row.
    """
    if account.provider != PROVIDER_GMAIL or account.email_address != PLACEHOLDER_EMAIL:
        return True
    token = await get_account_access_token(db, account)
    if not token:
        return False
    try:
        profile = await gs.get_gmail_profile(token)
    except Exception as exc:  # noqa: BLE001 — best-effort fill
        logger.warning("[email-accounts] profile lookup failed: %s", exc)
        return False
    address = str(profile.get("emailAddress") or "").strip()
    if not address:
        return False
    # Same-address row already exists (user reconnected before this ran) —
    # merge into it by re-pointing nothing and deleting the placeholder.
    existing = get_account_by_address(db, account.user_id, PROVIDER_GMAIL, address)
    if existing is not None and existing.id != account.id:
        credentials = _load_credentials(account)
        if credentials:
            existing.credentials = json.dumps(credentials)
        if account.watch_state and not existing.watch_state:
            existing.watch_state = account.watch_state
        if account.sync_cursor and not existing.sync_cursor:
            existing.sync_cursor = account.sync_cursor
        db.delete(account)
        db.commit()
        return True
    account.email_address = address[:320]
    if not account.display_name:
        account.display_name = address
    history_id = profile.get("historyId")
    if history_id is not None and not account.sync_cursor:
        account.sync_cursor = str(history_id)
    db.commit()

    # Re-link mail pushed for this address onto the gmail account, then drop
    # the now-orphaned n8n placeholder row when it holds no messages.
    n8n_row = get_account_by_address(db, account.user_id, PROVIDER_N8N, address)
    if n8n_row is not None:
        moved = (
            db.query(EmailMessage)
            .filter(EmailMessage.user_id == account.user_id, EmailMessage.account_id == n8n_row.id)
            .update({EmailMessage.account_id: account.id}, synchronize_session=False)
        )
        if moved:
            logger.info("[email-accounts] re-linked %s messages to gmail account %s", moved, account.id)
        remaining = (
            db.query(EmailMessage)
            .filter(EmailMessage.user_id == account.user_id, EmailMessage.account_id == n8n_row.id)
            .count()
        )
        if remaining == 0:
            db.delete(n8n_row)
        db.commit()
    return True


# ---------------------------------------------------------------------------
# Serialization (never includes credentials)
# ---------------------------------------------------------------------------


def serialize_account(account: EmailAccount) -> dict[str, Any]:
    """Public account shape — credentials stay server-side."""
    payload: dict[str, Any] = {
        "id": account.id,
        "provider": account.provider,
        "email_address": account.email_address,
        "display_name": account.display_name,
        "is_active": account.is_active,
        "has_credentials": bool(account.credentials),
        "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }
    if account.provider == PROVIDER_GMAIL:
        caps = account_capabilities(account)
        payload["capabilities"] = caps
        payload["watch"] = {
            "configured": gms.watch_configured(),
            "state": gms.get_watch_state(None, account),
        }
    return payload
