"""Helpers to determine whether the first-time setup flow is complete.

The app supports an unauthenticated "first boot" mode where the owner has not
yet configured `AUTH_PASSWORD` and `SECRET_KEY`. In that state only the setup
endpoints (`/config/setup`, `/config/setup-status`) and health checks may be
reached; every other endpoint must require a valid JWT.

These helpers centralise the "is setup complete?" check so auth, the setup
router and the WebSocket handshake all agree on the same definition.
"""

from __future__ import annotations

from pathlib import Path

# Known placeholder values that must never be accepted as a real SECRET_KEY.
# They are public in the repo / .env.example and would let an attacker forge
# JWTs. See issue #322.
SECRET_KEY_PLACEHOLDERS = frozenset({
    "",
    "dev_secret_change_me",
    "change_this_to_a_random_secret_key",
})

_ENV_FILE = Path("/app/.env") if Path("/app").exists() else Path(__file__).resolve().parent.parent.parent / ".env"


def _read_env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    if not _ENV_FILE.exists():
        return env
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def is_setup_complete() -> bool:
    """Return True when both AUTH_PASSWORD and a non-placeholder SECRET_KEY are configured.

    Uses the in-memory `settings` (populated from `.env` at startup and mutated
    by `/config/setup`). If the in-memory state says setup is incomplete we
    double-check the on-disk `.env` so a manually-edited file is still honoured
    without a restart. This avoids a file read on every authenticated request
    in the common (setup-complete) case.
    """
    from config import settings

    if settings.auth_password and is_secret_key_safe(settings.secret_key):
        return True

    # Fall back to disk to catch manual .env edits that haven't been reloaded.
    env = _read_env_file()
    has_password = bool(env.get("AUTH_PASSWORD"))
    secret = env.get("SECRET_KEY", "")
    has_secret = is_secret_key_safe(secret)
    return has_password and has_secret


def is_secret_key_safe(value: str) -> bool:
    """Return True if `value` is not a known public placeholder."""
    return value not in SECRET_KEY_PLACEHOLDERS
