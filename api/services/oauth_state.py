"""HMAC-signed OAuth ``state`` parameters (CSRF protection, #1280).

Stateless alternative to persisting a nonce per flow: the state embeds the
provider name, a random nonce and the issue timestamp, all covered by an
HMAC-SHA256 signature keyed with SECRET_KEY. Callbacks verify the signature
and TTL before any token exchange, so a forged, cross-provider or stale state
is rejected without a DB round-trip — and without a migration.

Format: ``<provider>.<nonce>.<issued_at>.<signature>``. Every segment is
URL-safe (``token_urlsafe``/digits/hex), so the token passes as a single
query-string value.

Reusable by Strava/Spotify when their flows land: ``generate_state("strava")``
in the auth-url endpoint, ``verify_state(state, "strava")`` in the callback.
"""

import hashlib
import hmac
import secrets
import time

from config import settings
from services.env_file import get_persisted

# OAuth consent flows complete in minutes; reject stale states so a leaked
# authorize URL cannot be replayed later.
STATE_TTL_SECONDS = 600


def _signing_key() -> str:
    """Current SECRET_KEY — same cross-worker lookup as ``auth_service``.

    ``settings.secret_key`` is loaded once at startup; ``get_persisted``
    re-reads the deployment .env so a key written by one uvicorn worker is
    visible to its siblings.
    """
    return get_persisted("SECRET_KEY") or settings.secret_key or ""


def _signature(key: str, payload: str) -> str:
    return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def generate_state(provider: str) -> str:
    """Create a signed OAuth state token for ``provider``.

    Raises ``RuntimeError`` when SECRET_KEY is not configured: an unsigned
    state would offer no CSRF protection, so failing the auth-url request is
    the safe outcome.
    """
    key = _signing_key()
    if not key:
        raise RuntimeError("SECRET_KEY not configured")
    nonce = secrets.token_urlsafe(16)
    issued_at = str(int(time.time()))
    payload = f"{provider}.{nonce}.{issued_at}"
    return f"{payload}.{_signature(key, payload)}"


def verify_state(state: str, provider: str, max_age: int = STATE_TTL_SECONDS) -> bool:
    """Return ``True`` only if ``state`` was signed for ``provider`` and fresh.

    Any deviation — missing key, wrong field count, foreign provider,
    malformed/future/expired timestamp or signature mismatch — is a plain
    ``False``; callers must deny the callback without leaking which check
    failed.
    """
    key = _signing_key()
    if not key or not state:
        return False
    parts = state.split(".")
    if len(parts) != 4:
        return False
    state_provider, nonce, issued_at, signature = parts
    if state_provider != provider:
        return False
    try:
        age = int(time.time()) - int(issued_at)
    except ValueError:
        return False
    if not 0 <= age <= max_age:
        return False
    payload = f"{state_provider}.{nonce}.{issued_at}"
    return hmac.compare_digest(_signature(key, payload), signature)


def seal_value(purpose: str, value: str) -> str:
    """Embed ``value`` in a signed token: ``<issued_at>.<value>.<signature>``.

    Used to hand a client an opaque handle for a server-side secret — e.g. the
    GitHub OAuth ``device_code`` (#1318) — so the raw secret never reaches the
    browser, a query string or the access logs, and the redemption endpoint
    can prove the handle was minted by this instance for ``purpose``.

    Raises ``RuntimeError`` when SECRET_KEY is not configured, mirroring
    ``generate_state``.
    """
    key = _signing_key()
    if not key:
        raise RuntimeError("SECRET_KEY not configured")
    issued_at = str(int(time.time()))
    signature = _signature(key, f"{purpose}.{issued_at}.{value}")
    return f"{issued_at}.{value}.{signature}"


def unseal_value(purpose: str, token: str, max_age: int = STATE_TTL_SECONDS) -> str | None:
    """Return the value embedded by ``seal_value``, or ``None`` if invalid.

    Any deviation — missing key, malformed token, foreign purpose,
    malformed/future/expired timestamp or signature mismatch — yields
    ``None``; callers must deny without leaking which check failed.
    """
    key = _signing_key()
    if not key or not token:
        return None
    issued_at, sep, rest = token.partition(".")
    if not sep:
        return None
    value, sep, signature = rest.rpartition(".")
    if not sep or not value or not signature:
        return None
    try:
        age = int(time.time()) - int(issued_at)
    except ValueError:
        return None
    if not 0 <= age <= max_age:
        return None
    expected = _signature(key, f"{purpose}.{issued_at}.{value}")
    if not hmac.compare_digest(expected, signature):
        return None
    return value
