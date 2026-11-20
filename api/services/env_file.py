"""Read/write access to the deployment's ``.env`` file.

Lives in ``services/`` because both ``routers/config.py`` (settings UI) and
``services/auth_service.py`` (cross-worker password lookup) need it, and a
router must never be imported from a service.
"""

import json
import logging
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _default_env_file() -> Path:
    """The deployment's ``.env`` when ``JOIDY_ENV_FILE`` is not set.

    ``/app/.env`` inside Docker (the compose bind-mount target), the repo-root
    ``.env`` otherwise.
    """
    if Path("/app").exists():
        return Path("/app/.env")
    return Path(__file__).parent.parent.parent / ".env"


def get_env_file() -> Path:
    """Resolve the env file path, honoring the ``JOIDY_ENV_FILE`` override.

    ``JOIDY_ENV_FILE`` already selects the host-side bind-mount source in
    docker-compose; honoring it in Python as well lets read-only installs and
    the test suite (#991) redirect persistence without touching the real
    ``.env``. Resolved on every call (not at import) so tests can point it at a
    per-test file after app modules are already imported.
    """
    return Path(os.getenv("JOIDY_ENV_FILE") or _default_env_file())


# Kept as a module-level constant for backwards compatibility (re-exported by
# ``routers/config.py``). Prefer ``get_env_file()`` — it picks up runtime
# changes to ``JOIDY_ENV_FILE``.
ENV_FILE = get_env_file()


# ── .env file permissions (#1281) ───────────────────────────────────────────
# .env holds every deployment secret (SECRET_KEY, POSTGRES_PASSWORD, OAuth
# client secrets, the AUTH_PASSWORD hash, INTERNAL_API_TOKEN, ...). Any mode
# looser than owner-only lets local users/processes read all of them, so:
#   * write_env() creates the file 0o600 and tightens pre-existing loose
#     files on every write;
#   * env_file_permissions() backs the API startup warning so files created
#     by hand or with a permissive umask get flagged even before the first
#     write.
# The CLI (`joidy` bootstrap) enforces the same 0o600 on every invocation;
# both together cover "create" and "mutate" paths on host and in-container.
ENV_FILE_MODE = 0o600


def env_file_permissions() -> int | None:
    """Permission bits of the env file (e.g. ``0o644``), or ``None``.

    ``None`` when the file does not exist or cannot be stat'ed — callers
    should treat that as "nothing to warn about".
    """
    env_file = get_env_file()
    try:
        return stat.S_IMODE(env_file.stat().st_mode)
    except OSError:
        return None


def _secure_env_file(env_file: Path) -> None:
    """Best-effort ``chmod 0o600``; a failure must never break a write."""
    try:
        os.chmod(env_file, ENV_FILE_MODE)
    except OSError as exc:
        logger.warning("could not restrict permissions on %s: %s", env_file, exc)


def read_env() -> dict:
    """Parse the env file into a dict, ignoring comments and blank lines.

    Uses ``is_file`` instead of ``exists``: when the bind mount source does not
    exist on the host, Docker silently creates /app/.env as a *directory* and
    ``open()`` raised IsADirectoryError, turning every /config request into a
    500 and breaking the whole settings page.
    """
    env_vars: dict[str, str] = {}
    env_file = get_env_file()
    if env_file.is_file():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


# ── .env value validation (#1312) ───────────────────────────────────────────
# Values persisted by write_env() must stay inert under *every* consumer.
# docker-compose treats them literally, but the file used to be `source`d by
# the Makefile — where $(...) and backticks execute as the host user — and a
# newline forges an extra KEY= line that read_env()'s last-wins parsing lets
# override a legit key (e.g. injected AUTH_PASSWORD beats the real one).
#
# Two layers:
#   * _assert_safe_chars() runs on EVERY value write_env() persists: rejects
#     control chars, quotes/backticks and $( / ${ expansion — the pieces that
#     make a value executable or forge additional lines. A poisoned key that
#     predates this fix therefore blocks further writes (fail closed) instead
#     of silently round-tripping.
#   * validate_env_value() adds per-key validators on top — the check the
#     routers run against *incoming* user values (POST /config, /config/setup).

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_EXPANSION_SEQUENCES = ("$(", "${", "`")

# Keys whose legitimate syntax requires double quotes. Kept deliberately tiny —
# a quoted value can break out of quoting contexts when a file is sourced.
_QUOTE_PERMITTED_KEYS = frozenset({"XP_TABLE_JSON"})

_TOKEN_RE = re.compile(r"[A-Za-z0-9_.:/@+=$-]+")  # API keys, secrets, bcrypt hashes ($2b$…)
_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")  # usernames, DB identifiers
_MODEL_RE = re.compile(r"[A-Za-z0-9_./:-]+")  # "provider:model" refs, image tags
_INT_RE = re.compile(r"[0-9]+")
_BOOL_RE = re.compile(r"(true|false|yes|no|0|1)", re.IGNORECASE)
_APP_ENV_RE = re.compile(r"[a-z_]+")
_TZ_RE = re.compile(r"[A-Za-z0-9_+/\-]+")  # IANA names: UTC, America/Santiago, Etc/GMT-3
_CRON_RE = re.compile(r"[0-9*,/ -]+|@(hourly|daily|weekly|monthly|yearly|annually|reboot)")
_CORS_ORIGINS_RE = re.compile(r"[A-Za-z0-9_.:/, \-*]+")  # CSV origins, '*' wildcard
_EMAIL_RE = re.compile(r"(mailto:)?[A-Za-z0-9_.@+\-]+")
_PATH_START_RE = re.compile(r"[~/.\w]")  # paths must not start with '-' or shell metachars


def _assert_safe_chars(key: str, value: str) -> None:
    """Reject values that could execute or forge lines if .env were sourced.

    Applied to every value write_env() persists — including keys already on
    disk — so a value smuggled in before this fix cannot keep re-writing.
    """
    if _CONTROL_CHARS_RE.search(value):
        raise ValueError(f"{key}: control characters are not allowed in .env values")
    for seq in _EXPANSION_SEQUENCES:
        if seq in value:
            raise ValueError(f"{key}: '{seq}' is not allowed in .env values")
    if "'" in value:
        raise ValueError(f"{key}: single quotes are not allowed in .env values")
    if '"' in value and key not in _QUOTE_PERMITTED_KEYS:
        raise ValueError(f"{key}: double quotes are not allowed in .env values")


def _regex_validator(pattern: re.Pattern, description: str) -> Callable[[str, str], str]:
    def check(key: str, value: str) -> str:
        if not pattern.fullmatch(value):
            raise ValueError(f"{key}: expected {description} (got {value!r})")
        return value

    return check


def _validate_path_value(key: str, value: str) -> str:
    """Absolute, ~-relative or ./-relative POSIX path; normalized on return."""
    if "\\" in value or not _PATH_START_RE.match(value):
        raise ValueError(f"{key}: expected a filesystem path (got {value!r})")
    return os.path.normpath(value)


def _validate_rel_folder_value(key: str, value: str) -> str:
    """Relative folder inside the vault — no absolute paths or '..' escapes."""
    if "\\" in value or value.startswith(("/", "~")) or ".." in PurePosixPath(value).parts:
        raise ValueError(f"{key}: expected a relative folder inside the vault (got {value!r})")
    return os.path.normpath(value)


def _validate_url_value(key: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{key}: expected an http(s) URL (got {value!r})")
    return value


def _validate_json_value(key: str, value: str) -> str:
    try:
        json.loads(value)
    except (ValueError, TypeError):
        raise ValueError(f"{key}: expected valid JSON (got {value!r})") from None
    return value


def _validate_port_value(key: str, value: str) -> str:
    if not _INT_RE.fullmatch(value) or not (0 < int(value) <= 65535):
        raise ValueError(f"{key}: expected a TCP port 1-65535 (got {value!r})")
    return value


_TOKEN_DESC = "letters, digits and _ - . : / @ + = $ only"
_KEY_VALIDATORS: dict[str, Callable[[str, str], str]] = {
    # Paths & folders
    "OBSIDIAN_VAULT_PATH": _validate_path_value,
    "DOCKER_SOCK_PATH": _validate_path_value,
    "JOIDY_BACKUP_DIR": _validate_path_value,
    "JOIDY_DATA_DIR": _validate_path_value,
    "JOIDY_ENV_FILE": _validate_path_value,
    "LOG_DIR": _validate_path_value,
    "UPLOAD_DIR": _validate_path_value,
    "DAILY_NOTES_FOLDER": _validate_rel_folder_value,
    # URLs
    "OPENAI_BASE_URL": _validate_url_value,
    "OLLAMA_BASE_URL": _validate_url_value,
    "GOOGLE_REDIRECT_URI": _validate_url_value,
    "STRAVA_REDIRECT_URI": _validate_url_value,
    "SPOTIFY_REDIRECT_URI": _validate_url_value,
    "GITHUB_OAUTH_WEB_URL": _validate_url_value,
    "GITHUB_WEBHOOK_URL": _validate_url_value,
    "N8N_WEBHOOK_URL": _validate_url_value,
    # Secrets & API tokens (AUTH_PASSWORD stores a bcrypt hash: "$2b$12$…")
    "GEMINI_API_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "OPENAI_API_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "ANTHROPIC_API_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "COHERE_API_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "OPENROUTER_API_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "GITHUB_TOKEN": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "GITHUB_CLIENT_ID": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "GITHUB_CLIENT_SECRET": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "GOOGLE_CLIENT_ID": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "GOOGLE_CLIENT_SECRET": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "STRAVA_CLIENT_ID": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "STRAVA_CLIENT_SECRET": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "SPOTIFY_CLIENT_ID": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "SPOTIFY_CLIENT_SECRET": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "TELEGRAM_BOT_TOKEN": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "SECRET_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "INTERNAL_SECRET": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "AUTH_PASSWORD": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "POSTGRES_PASSWORD": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "GRAFANA_ADMIN_PASSWORD": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "OBSIDIAN_WEBHOOK_SECRET": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "N8N_ENCRYPTION_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "VAPID_PUBLIC_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    "VAPID_PRIVATE_KEY": _regex_validator(_TOKEN_RE, _TOKEN_DESC),
    # Names & identifiers
    "GITHUB_USERNAME": _regex_validator(_NAME_RE, "letters, digits, '-' and '_' only"),
    "POSTGRES_USER": _regex_validator(_NAME_RE, "letters, digits, '-' and '_' only"),
    "POSTGRES_DB": _regex_validator(_NAME_RE, "letters, digits, '-' and '_' only"),
    "LLM_MODEL": _regex_validator(_MODEL_RE, "a 'provider:model' reference"),
    "EMBEDDING_MODEL": _regex_validator(_MODEL_RE, "a 'provider:model' reference"),
    "DOCKER_REGISTRY": _regex_validator(_MODEL_RE, "a registry/repository reference"),
    "POSTGRES_IMAGE": _regex_validator(_MODEL_RE, "an image:tag reference"),
    "IMAGE_TAG": _regex_validator(_MODEL_RE, "an image tag"),
    # Numeric / enum-like
    "TELEGRAM_ALLOWED_USER_ID": _regex_validator(_INT_RE, "digits only"),
    "DOCKER_GID": _regex_validator(_INT_RE, "digits only"),
    "LLM_MAX_TOKENS": _regex_validator(_INT_RE, "digits only"),
    "BCRYPT_ROUNDS": _regex_validator(_INT_RE, "digits only"),
    "BACKUP_RETENTION_DAYS": _regex_validator(_INT_RE, "digits only"),
    "BACKUP_RETENTION_WEEKS": _regex_validator(_INT_RE, "digits only"),
    "BACKUP_WEEKLY_DAY": _regex_validator(_INT_RE, "digits only"),
    "JOIDY_IDLE_TIMEOUT": _regex_validator(_INT_RE, "digits only"),
    "JOIDY_IDLE_POLL_SECONDS": _regex_validator(_INT_RE, "digits only"),
    "ESBUILD_WORKERS": _regex_validator(_INT_RE, "digits only"),
    "FRONTEND_PORT": _validate_port_value,
    "API_PORT": _validate_port_value,
    "AI_SERVICE_PORT": _validate_port_value,
    "WORKER_PORT": _validate_port_value,
    "N8N_PORT": _validate_port_value,
    "AI_SERVICE_ENABLED": _regex_validator(_BOOL_RE, "true/false"),
    "BACKUP_ENABLED": _regex_validator(_BOOL_RE, "true/false"),
    "BACKUP_ON_START": _regex_validator(_BOOL_RE, "true/false"),
    "APP_ENV": _regex_validator(_APP_ENV_RE, "a lowercase environment name"),
    "USER_TIMEZONE": _regex_validator(_TZ_RE, "an IANA timezone name"),
    "BACKUP_SCHEDULE": _regex_validator(_CRON_RE, "a cron expression"),
    "CORS_ALLOWED_ORIGINS": _regex_validator(_CORS_ORIGINS_RE, "a comma-separated origin list"),
    "VAPID_CLAIM_EMAIL": _regex_validator(_EMAIL_RE, "an email or mailto: address"),
    "XP_TABLE_JSON": _validate_json_value,
}


def validate_env_value(key: str, value: str) -> str:
    """Validate a single value destined for the .env file; return what to store.

    Raises ``ValueError`` when the value could forge extra ``KEY=`` lines or
    execute under shell sourcing (#1312). May normalize (e.g. paths via
    ``os.path.normpath``). Empty values mean "cleared" and are always allowed.
    Routers map the error to HTTP 400.
    """
    if not isinstance(value, str):
        value = str(value)
    if value == "":
        return value
    _assert_safe_chars(key, value)
    validator = _KEY_VALIDATORS.get(key)
    if validator is not None:
        return validator(key, value)
    return value


def write_env(env_vars: dict) -> None:
    """Persist ``env_vars`` while keeping the file's comments and layout.

    The previous implementation rewrote the file from scratch as a flat list of
    ``KEY=VALUE`` lines, which destroyed every comment and commented-out
    template entry the user (or ``.env.example``) had — including the hints
    needed to configure the app later.

    Raises ``ValueError`` — before touching the file — if any value could
    forge extra ``KEY=`` lines or execute under shell sourcing (#1312). This
    is the universal character check; the stricter per-key validators run at
    the API boundary via ``validate_env_value``.
    """
    for key, value in env_vars.items():
        _assert_safe_chars(key, str(value))

    env_file = get_env_file()
    lines: list[str] = []
    if env_file.is_file():
        with open(env_file) as f:
            lines = f.read().splitlines()

    remaining = dict(env_vars)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)

    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    # os.open with mode 0o600 so a *new* file is never readable by other
    # users even under a permissive umask (umask can only strip bits), then
    # chmod to tighten files that predate this fix or were created by hand
    # with a loose mode (#1281).
    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, ENV_FILE_MODE)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(output).rstrip("\n") + "\n")
    _secure_env_file(env_file)


def get_persisted(key: str) -> str:
    """Read a single key straight from disk.

    Needed because uvicorn runs with ``--workers``: a value written by the
    worker that handled a request is invisible to its siblings, whose in-memory
    ``settings`` object still holds the value loaded at startup.
    """
    return read_env().get(key, "")
