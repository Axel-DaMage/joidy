"""
JWT Authentication Service.
"""

import ipaddress
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from config import settings
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from services.env_file import get_effective_secret, get_persisted

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ISSUER = "joidy-api"
AUDIENCE = "joidy-app"
TOKEN_TYPE_ACCESS = "access"  # noqa: S105 — JWT typ claim label, not a password
TOKEN_TYPE_REFRESH = "refresh"  # noqa: S105 — JWT typ claim label, not a password

security = HTTPBearer(auto_error=False)
# bcrypt cost factor (default 12). Tests lower it via BCRYPT_ROUNDS (#996);
# passlib was dropped for direct bcrypt use — passlib 1.7.4 is unmaintained
# and breaks on bcrypt >= 4.1 (#1290).
_BCRYPT_ROUNDS: int = settings.bcrypt_rounds or 12


def _effective_auth_password() -> str:
    """Return the current AUTH_PASSWORD, reading from disk on every call.

    Uvicorn runs with ``--workers 2``: ``settings.auth_password`` is loaded
    once at startup and ``POST /config/setup`` only updates the worker that
    served the request. Reading the persisted value here ensures every
    worker sees the same password immediately after setup, with no restart
    needed.
    """
    return get_persisted("AUTH_PASSWORD") or settings.auth_password or ""


def _effective_secret_key() -> str:
    """Return the current SECRET_KEY, reading from disk on every call.

    Same cross-worker rationale as ``_effective_auth_password``: tokens
    signed by the worker that ran setup must verify on its siblings.

    Placeholder values shipped in .env.example (and common weak stand-ins)
    are treated as unset (#1393): a signing key published in the repository
    would let anyone forge JWTs, so token creation must fail closed.
    """
    return get_effective_secret("SECRET_KEY", settings.secret_key)


def signing_secret() -> str:
    """Current JWT signing secret.

    Public accessor so the rate-limit middleware can validate Bearer tokens
    (``jwt.decode`` directly, without the per-request warning logs of
    ``verify_token``) while still picking up secret rotation across workers.
    """
    return _effective_secret_key()


def _effective_internal_api_token() -> str:
    """Return the current INTERNAL_API_TOKEN, reading from disk on every call.

    Same cross-worker rationale as ``_effective_auth_password``. Placeholder
    values are rejected the same way as SECRET_KEY (#1393): an internal token
    set to a publicly known value would let anyone impersonate a service.
    """
    return get_effective_secret("INTERNAL_API_TOKEN", settings.internal_api_token)


def verify_internal_token(token: str) -> bool:
    """Return True when ``token`` matches the configured INTERNAL_API_TOKEN."""
    expected = _effective_internal_api_token()
    return bool(expected) and secrets.compare_digest(token, expected)


def verify_password(plain: str, stored: str) -> bool:
    """Verify a password against a stored hash or plaintext.

    Supports bcrypt hashes (starting with $2b$) and plaintext for backward
    compat. The plaintext path is DEPRECATED (#1265) and only exists so .env
    files written before hashing was introduced keep working — the lifespan
    logs a loud warning via ``warn_if_plaintext_auth_password`` whenever it
    is in effect.
    """
    if stored.startswith("$2b$"):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            # Malformed stored hash: report a non-match instead of a 500,
            # matching the behaviour passlib's CryptContext.verify provided.
            return False
    return secrets.compare_digest(plain, stored)


def is_plaintext_stored_password(stored: str) -> bool:
    """True when ``stored`` would authenticate via the plaintext fallback.

    Mirrors ``verify_password``: only ``$2b$`` values are treated as bcrypt,
    so anything else — including hand-edited .env entries predating hashing —
    takes the constant-time plaintext compare.
    """
    return bool(stored) and not stored.startswith("$2b$")


def warn_if_plaintext_auth_password() -> None:
    """Log a loud warning when the effective AUTH_PASSWORD is plaintext.

    Backward compat only (#1265): the setup flow always writes a bcrypt hash,
    so a plaintext value means a hand-edited .env predating hashing — prod
    auth is then running on a raw secret with no indication it is weak. The
    plaintext path in ``verify_password`` is deprecated and scheduled for
    removal; this warning is the migration nudge.
    """
    if is_plaintext_stored_password(_effective_auth_password()):
        logger.warning(
            "AUTH_PASSWORD is stored in PLAINTEXT (not a bcrypt hash). This deprecated "
            "fallback will be removed in a future release — remove AUTH_PASSWORD from "
            ".env and complete the setup wizard again (POST /config/setup) to store a "
            "bcrypt hash instead."
        )


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def _create_token(user_id: int, username: str, token_type: str, lifetime: timedelta) -> str:
    """Sign a JWT with the registered claims enforced at verify time (#1285).

    ``iat``/``iss``/``aud`` make every token attributable to this deployment
    (an ``iss``/``aud`` mismatch is rejected on decode); ``typ`` keeps refresh
    tokens from being replayed as access tokens; ``jti`` uniquely identifies
    each refresh token so rotated credentials are never identical.
    """
    secret = _effective_secret_key()
    if not secret:
        raise ValueError("SECRET_KEY not configured")

    now = datetime.now(UTC)
    claims: dict = {
        "sub": str(user_id),
        "exp": now + lifetime,
        "iat": now,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "typ": token_type,
    }
    if username:
        claims["username"] = username
    if token_type == TOKEN_TYPE_REFRESH:
        claims["jti"] = secrets.token_urlsafe(16)
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def create_access_token(user_id: int, username: str = "user") -> str:
    """Create a short-lived JWT access token (#1285)."""
    return _create_token(
        user_id,
        username,
        TOKEN_TYPE_ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int, username: str = "user") -> str:
    """Create a long-lived JWT refresh token for ``POST /auth/refresh`` (#1285).

    The token is only accepted by the refresh endpoint (``typ=refresh``);
    each call returns a new ``jti`` so refreshes rotate the credential.
    """
    return _create_token(
        user_id,
        username,
        TOKEN_TYPE_REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
    )


def verify_token(token: str, expected_type: str = TOKEN_TYPE_ACCESS) -> dict | None:
    """Verify and decode a JWT token.

    Enforces the registered claims: signature, ``exp``, ``iss``, ``aud``,
    numeric ``iat``, plus the ``typ`` discriminant — a refresh token is
    rejected wherever an access token is expected and vice versa (#1285).
    """
    secret = _effective_secret_key()
    if not secret:
        logger.warning("SECRET_KEY not configured, token verification skipped")
        return None

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None

    token_type = payload.get("typ")
    if token_type != expected_type:
        logger.warning(f"Unexpected token type {token_type!r} (expected {expected_type!r})")
        return None
    return payload


def get_current_user_id(token: str) -> int | None:
    """Extract user ID from token."""
    payload = verify_token(token)
    if payload:
        return int(payload.get("sub", 0))
    return None


def _is_loopback(host: str | None) -> bool:
    """Return True only when ``host`` is a literal loopback IP (127.0.0.0/8, ::1).

    Anything that is not a loopback IP — public/private addresses, empty
    strings, hostnames, malformed values — fails closed (#1282). IPv4-mapped
    IPv6 addresses (``::ffff:127.0.0.1``) are unwrapped before the check so
    dual-stack dev setups still count as loopback.
    """
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def _connection_host(conn) -> str | None:
    """Extract the peer host from a Request or WebSocket (None when absent)."""
    client = getattr(conn, "client", None)
    return client.host if client else None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int | None:
    """Dependency to get current user from Bearer token.

    In development without AUTH_PASSWORD, auth is bypassed for loopback
    clients only (#1282): a request arriving via a non-loopback interface
    means the dev server is exposed to the LAN and must present a valid
    token like any authenticated deployment.
    In production, auth is always required — missing AUTH_PASSWORD means
    no valid token can be issued, so all requests are rejected.
    """
    auth_password = _effective_auth_password()
    if not auth_password:
        if settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication not configured. Set AUTH_PASSWORD in .env.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        client_host = _connection_host(request)
        if _is_loopback(client_host):
            return 1
        # Non-loopback dev client: fall through to token validation.
        if not credentials:
            logger.warning(
                "Rejected unauthenticated request from non-loopback client %s (dev auth bypass is loopback-only)",
                client_host,
            )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = get_current_user_id(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def get_current_user_or_internal(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int | None:
    """Dedicated dependency for routes also reachable by internal services.

    Accepts ``Authorization: Bearer <INTERNAL_API_TOKEN>`` (worker, n8n) in
    addition to a user JWT. The service token is validated here and never
    goes through ``/auth/login`` or ``verify_password`` — it is unrelated to
    ``AUTH_PASSWORD`` (#1275).
    """
    if credentials and verify_internal_token(credentials.credentials):
        return 1
    return get_current_user(request, credentials)
