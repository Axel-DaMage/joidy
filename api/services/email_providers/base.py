"""Email provider abstraction (#1659).

The contract every mailbox provider implements so the native mail clients
stay provider-agnostic. Gmail ships first (``gmail.py``); Outlook (Microsoft
Graph) and generic IMAP slot in by subclassing ``EmailProvider`` and
registering in ``__init__.py`` — no schema change, because
``email_accounts.credentials``/``sync_cursor``/``watch_state`` are opaque
per-provider payloads.

Adding a provider
-----------------
1. ``EmailAccount.provider`` gets a new value (``PROVIDER_*`` constant in
   ``models/email_account.py``).
2. Subclass ``EmailProvider``, implement the abstract members, register the
   instance in ``services/email_providers/__init__.py``.
3. Define the shape of the account's ``credentials`` JSON blob and the
   meaning of its ``sync_cursor`` (e.g. Gmail historyId, IMAP UID, Graph
   deltaToken) — both are opaque to everything outside the provider.
4. ``normalize()`` must return a ``NormalizedEmail`` so any provider yields
   the same provider-agnostic message shape.

Providers without a changes feed or push support raise
``ProviderCapabilityError`` from those methods; callers then fall back to a
bounded ``list_messages`` poll.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypedDict


class ProviderCapabilityError(RuntimeError):
    """The provider does not support this operation (→ HTTP 501/503)."""


class NormalizedEmail(TypedDict, total=False):
    """Provider-agnostic normalized message shape.

    ``remote_id`` is the provider's stable message id (the Gmail message id
    for ``provider="gmail"``).
    """

    remote_id: str
    thread_id: str | None
    subject: str | None
    sender: str | None
    snippet: str | None
    body_text: str | None
    received_at: datetime | None
    unread: bool
    important: bool
    importance_reason: str | None
    labels: list[str]


class EmailProvider(ABC):
    """Contract for a mailbox provider bound to one ``EmailAccount`` row.

    Implementations receive the decrypted ``credentials`` JSON blob (never
    the raw column) and must not mutate it — token refresh/persistence is
    owned by ``email_account_service``.
    """

    #: Value stored in ``email_accounts.provider``.
    provider: str = ""

    @abstractmethod
    async def list_messages(
        self,
        credentials: dict[str, Any],
        *,
        query: str | None = None,
        since: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """One page of provider message summaries + pagination state."""

    async def list_changes(
        self,
        credentials: dict[str, Any],
        *,
        cursor: str,
        max_results: int = 100,
        page_token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Incremental changes since ``cursor`` (the account's opaque
        ``sync_cursor`` — Gmail historyId, IMAP UID, Graph deltaToken).

        Providers without a changes feed raise the default
        ``ProviderCapabilityError``; callers then fall back to a bounded
        ``list_messages`` backfill."""
        raise ProviderCapabilityError(f"{self.provider} does not expose a changes feed")

    @abstractmethod
    async def get_message(self, credentials: dict[str, Any], message_id: str) -> dict[str, Any]:
        """Full provider message resource for ``message_id``."""

    @abstractmethod
    async def watch(self, credentials: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Register a push subscription; returns state persisted in
        ``account.watch_state``. Push-only providers raise
        ``ProviderCapabilityError``."""

    @abstractmethod
    async def stop_watch(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Tear down the push subscription registered by ``watch``."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> NormalizedEmail:
        """Provider message resource → ``NormalizedEmail`` for upsert."""
