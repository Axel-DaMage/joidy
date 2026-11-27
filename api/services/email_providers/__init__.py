"""Provider registry (#1659).

``get_provider(name)`` returns the ``EmailProvider`` implementation bound to
an ``EmailAccount.provider`` value. Registering a new provider (Outlook via
Microsoft Graph, generic IMAP) is: implement ``EmailProvider`` in a module
here, add the ``PROVIDER_*`` constant in ``models/email_account.py`` and map
it in ``_PROVIDERS`` — no schema or call-site changes.
"""

from services.email_providers.base import EmailProvider, NormalizedEmail, ProviderCapabilityError
from services.email_providers.gmail import GmailProvider
from services.email_providers.n8n import N8nProvider

_PROVIDERS: dict[str, EmailProvider] = {
    GmailProvider.provider: GmailProvider(),
    N8nProvider.provider: N8nProvider(),
}


def get_provider(name: str) -> EmailProvider:
    """Return the registered provider for ``name`` or raise KeyError."""
    return _PROVIDERS[name]


def supported_providers() -> list[str]:
    return sorted(_PROVIDERS)


__all__ = [
    "EmailProvider",
    "NormalizedEmail",
    "ProviderCapabilityError",
    "get_provider",
    "supported_providers",
]
