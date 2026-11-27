"""n8n ingestion provider (#1659).

n8n is a push channel, not a credentialled mailbox API: its workflow POSTs
normalized messages to ``/emails`` and the local rows are authoritative —
there is nothing to list, fetch or watch upstream. The provider exists so
``EmailAccount(provider="n8n")`` rows are first-class accounts in the
registry (auto-created by the inbox upsert so ``account_id`` is always
populated), while poll/watch operations raise ``ProviderCapabilityError``.
"""

from typing import Any

from models.email_account import PROVIDER_N8N
from services.email_providers.base import EmailProvider, NormalizedEmail, ProviderCapabilityError


class N8nProvider(EmailProvider):
    provider = PROVIDER_N8N

    def _unsupported(self, op: str) -> ProviderCapabilityError:
        return ProviderCapabilityError(f"n8n is a push ingestion channel — {op} is not available")

    async def list_messages(self, credentials: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise self._unsupported("list_messages")

    async def get_message(self, credentials: dict[str, Any], message_id: str) -> dict[str, Any]:
        raise self._unsupported("get_message")

    async def watch(self, credentials: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise self._unsupported("watch")

    async def stop_watch(self, credentials: dict[str, Any]) -> dict[str, Any]:
        raise self._unsupported("stop_watch")

    def normalize(self, raw: dict[str, Any]) -> NormalizedEmail:
        """The n8n payload already arrives normalized (it's the
        ``EmailUpsert`` schema); map it onto the canonical shape."""
        from datetime import datetime

        received_at = None
        raw_dt = raw.get("received_at")
        if isinstance(raw_dt, datetime):
            received_at = raw_dt
        elif raw_dt:
            try:
                received_at = datetime.fromisoformat(str(raw_dt).replace("Z", "+00:00"))
            except ValueError:
                received_at = None
        return {
            "remote_id": str(raw.get("gmail_id") or raw.get("remote_id") or ""),
            "thread_id": raw.get("thread_id"),
            "subject": raw.get("subject"),
            "sender": raw.get("sender"),
            "snippet": raw.get("snippet"),
            "body_text": raw.get("body_text"),
            "received_at": received_at,
            "unread": bool(raw.get("unread", True)),
            "important": bool(raw.get("important", False)),
            "importance_reason": raw.get("importance_reason"),
            "labels": list(raw.get("labels") or []),
        }
