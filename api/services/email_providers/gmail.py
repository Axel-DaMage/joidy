"""Gmail provider implementation (#1659).

Wraps ``services.gmail_service`` so an ``EmailAccount(provider="gmail")``
behaves like any other ``EmailProvider``. The account's ``credentials`` blob
carries ``{access_token, refresh_token, expires_at, scope, token_type}``;
``sync_cursor`` is the Gmail ``historyId`` used by ``list_changes`` →
``users.history.list``; ``watch_state`` is the ``users.watch`` registration
record.
"""

from typing import Any

from models.email_account import PROVIDER_GMAIL
from services import gmail_service as gms
from services.email_providers.base import EmailProvider, NormalizedEmail


class GmailProvider(EmailProvider):
    provider = PROVIDER_GMAIL

    @staticmethod
    def _token(credentials: dict[str, Any]) -> str:
        """Access token inside the decrypted credentials blob."""
        return str(credentials.get("access_token") or "")

    async def list_messages(
        self,
        credentials: dict[str, Any],
        *,
        query: str | None = None,
        since: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        return await gms.list_messages(
            self._token(credentials),
            q=query,
            since=since,
            max_results=max_results,
            page_token=page_token,
        )

    async def list_changes(
        self,
        credentials: dict[str, Any],
        *,
        cursor: str,
        max_results: int = 100,
        page_token: str | None = None,
        label_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """users.history.list — the historyId cursor is Gmail's incremental
        sync position."""
        return await gms.get_history(
            self._token(credentials),
            start_history_id=cursor,
            page_token=page_token,
            max_results=max_results,
            label_id=label_id,
        )

    async def get_message(self, credentials: dict[str, Any], message_id: str) -> dict[str, Any]:
        return await gms.get_message(self._token(credentials), message_id)

    async def watch(self, credentials: dict[str, Any], label_ids: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        """users.watch — callers persist the returned dict on
        ``account.watch_state`` (topic/historyId/expiration)."""
        return await gms.request_watch(self._token(credentials), label_ids=label_ids)

    async def stop_watch(self, credentials: dict[str, Any]) -> dict[str, Any]:
        return await gms.request_stop_watch(self._token(credentials))

    def normalize(self, raw: dict[str, Any]) -> NormalizedEmail:
        """Full-message dict (already flattened by ``normalize_message``) →
        upsert-ready fields."""
        received_at = None
        if raw.get("internal_date"):
            from datetime import datetime

            try:
                received_at = datetime.fromisoformat(str(raw["internal_date"]).replace("Z", "+00:00"))
            except ValueError:
                received_at = None
        headers = raw.get("headers") or {}
        labels = raw.get("label_ids") or []
        return {
            "remote_id": str(raw.get("id") or ""),
            "thread_id": raw.get("thread_id"),
            "subject": headers.get("subject"),
            "sender": headers.get("from"),
            "snippet": raw.get("snippet"),
            "body_text": raw.get("body_text"),
            "received_at": received_at,
            "unread": gms.LABEL_UNREAD in labels,
            "important": "IMPORTANT" in labels,
            "labels": list(labels),
        }
