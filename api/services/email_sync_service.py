"""Per-account email sync into the unified inbox (#1659).

Each ``EmailAccount`` owns an opaque ``sync_cursor`` (Gmail historyId) and
``last_sync_at`` — syncing one mailbox never touches another's position.
Two modes:

- **Backfill** (no cursor): bounded ``list_messages`` page → per-message
  ``get_message`` → ``normalize`` → ``upsert_email``; the cursor is seeded
  from the profile's current historyId.
- **Incremental** (cursor present): ``list_changes`` (users.history.list)
  pages → messagesAdded/label changes are fetched + upserted,
  messagesDeleted drop the local row. A stale/expired cursor (Gmail answers
  404) falls back to a fresh backfill.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from models.email_account import PROVIDER_GMAIL, EmailAccount
from models.email_message import EmailMessage
from services import email_account_service as eas
from services import google_service as gs
from services.email_providers import ProviderCapabilityError, get_provider
from services.email_service import upsert_email
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Hard bounds so a manual sync stays a bounded request.
MAX_SYNC_MESSAGES = 50
MAX_HISTORY_PAGES = 5


class AccountNotConnected(RuntimeError):
    """The account has no usable credentials — it must be re-connected."""


class ProviderNotSyncable(RuntimeError):
    """The account's provider has no pull API (e.g. n8n push ingestion)."""


async def _account_token(db: Session, account: EmailAccount) -> str:
    """Resolve a live access token for the account, filling the pending
    email_address placeholder first when needed."""
    if account.provider == PROVIDER_GMAIL:
        await eas.resolve_pending_profile(db, account)
        token = await eas.get_account_access_token(db, account)
        if token:
            return token
    raise AccountNotConnected("La cuenta no está conectada — vuelve a vincularla en Ajustes")


def _upsert_normalized(db: Session, account: EmailAccount, normalized: dict[str, Any]) -> None:
    """Feed one provider-normalized message into the inbox rows."""
    upsert_email(
        db,
        account.user_id,
        account=account.email_address,
        gmail_id=normalized["remote_id"],
        thread_id=normalized.get("thread_id"),
        subject=normalized.get("subject"),
        sender=normalized.get("sender"),
        snippet=normalized.get("snippet"),
        body_text=normalized.get("body_text"),
        received_at=normalized.get("received_at"),
        unread=normalized.get("unread", True),
        important=normalized.get("important", False),
        importance_reason=normalized.get("importance_reason"),
        labels=normalized.get("labels"),
        account_id=account.id,
    )


async def _fetch_and_upsert(db: Session, provider, credentials: dict, account: EmailAccount, message_id: str) -> bool:
    try:
        raw = await provider.get_message(credentials, message_id)
    except Exception:  # noqa: BLE001 — one bad message must not fail the sync
        logger.warning("[email-sync] fetch failed for %s on account %s", message_id, account.id, exc_info=True)
        return False
    normalized = provider.normalize(raw)
    if not normalized.get("remote_id"):
        return False
    _upsert_normalized(db, account, normalized)
    return True


async def _backfill(db: Session, provider, credentials: dict, account: EmailAccount) -> dict[str, Any]:
    """No cursor (or expired one): pull the newest page, seed the cursor from
    the mailbox profile."""
    page = await provider.list_messages(credentials, max_results=MAX_SYNC_MESSAGES)
    synced = 0
    for stub in page.get("messages") or []:
        message_id = stub.get("id")
        if message_id and await _fetch_and_upsert(db, provider, credentials, account, message_id):
            synced += 1
    # Refresh the cursor from the mailbox head — every fetched message is at
    # or below it, so next sync only walks newer history.
    if account.provider == PROVIDER_GMAIL:
        profile = await gs.get_gmail_profile(credentials["access_token"])
        history_id = profile.get("historyId")
        if history_id is not None:
            account.sync_cursor = str(history_id)
    return {"mode": "backfill", "synced": synced}


def _deleted_local_ids(db: Session, account: EmailAccount, gmail_ids: list[str]) -> int:
    if not gmail_ids:
        return 0
    return (
        db.query(EmailMessage)
        .filter(
            EmailMessage.user_id == account.user_id,
            EmailMessage.account_id == account.id,
            EmailMessage.gmail_id.in_(gmail_ids),
        )
        .delete(synchronize_session=False)
    )


async def _incremental(db: Session, provider, credentials: dict, account: EmailAccount) -> dict[str, Any]:
    """Walk history pages from the stored cursor; upsert affected messages."""
    if account.sync_cursor is None:
        raise ProviderNotSyncable("incremental sync requires a stored cursor")
    changed_ids: list[str] = []
    deleted_ids: list[str] = []
    next_page: str | None = None
    history_id = account.sync_cursor
    pages = 0
    while pages < MAX_HISTORY_PAGES:
        data = await provider.list_changes(
            credentials,
            cursor=account.sync_cursor,
            page_token=next_page,
        )
        pages += 1
        if data.get("history_id"):
            history_id = str(data["history_id"])
        for record in data.get("records") or []:
            for ref in record.get("messages_added") or []:
                if ref.get("id"):
                    changed_ids.append(ref["id"])
            for ref in record.get("messages_deleted") or []:
                if ref.get("id"):
                    deleted_ids.append(ref["id"])
            for change in (record.get("labels_added") or []) + (record.get("labels_removed") or []):
                if change.get("message_id"):
                    changed_ids.append(change["message_id"])
        next_page = data.get("next_page_token")
        if not next_page:
            break

    synced = 0
    for message_id in list(dict.fromkeys(changed_ids))[:MAX_SYNC_MESSAGES]:
        if await _fetch_and_upsert(db, provider, credentials, account, message_id):
            synced += 1
    removed = _deleted_local_ids(db, account, deleted_ids)
    account.sync_cursor = history_id
    return {"mode": "incremental", "synced": synced, "deleted": removed, "history_pages": pages}


async def sync_account(
    db: Session,
    user_id: int,
    account: EmailAccount,
) -> dict[str, Any]:
    """Sync one provider account into ``email_messages`` under its own cursor.

    Raises ``ProviderNotSyncable`` for push-only providers and
    ``AccountNotConnected`` when credentials can't produce a token.
    """
    if account.provider == PROVIDER_GMAIL:
        token = await _account_token(db, account)
        credentials = {"access_token": token}
        provider = get_provider(account.provider)
        try:
            if account.sync_cursor:
                try:
                    result = await _incremental(db, provider, credentials, account)
                except (ProviderCapabilityError, httpx.HTTPStatusError) as exc:
                    # Gmail answers 404 when the historyId is too old —
                    # resync from scratch instead of failing the account.
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if not isinstance(exc, httpx.HTTPStatusError) or status != 404:
                        raise
                    logger.info("[email-sync] stale cursor on account %s — backfilling", account.id)
                    account.sync_cursor = None
                    result = await _backfill(db, provider, credentials, account)
            else:
                result = await _backfill(db, provider, credentials, account)
        except Exception:
            db.rollback()
            raise
    else:
        raise ProviderNotSyncable(f"provider {account.provider} has no pull sync — mail arrives by push")

    account.last_sync_at = datetime.now(UTC)
    db.commit()
    result["account_id"] = account.id
    result["cursor"] = account.sync_cursor
    return result
