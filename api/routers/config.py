import ipaddress
import os
import secrets

from config import settings
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from services.auth_service import get_current_user, hash_password
from services.env_file import ENV_FILE, read_env, validate_env_value, write_env  # noqa: F401  (ENV_FILE re-exported)

router = APIRouter(prefix="/config", tags=["config"])

CONFIG_KEYS = {
    "gemini_api_key": "GEMINI_API_KEY",
    "obsidian_vault_path": "OBSIDIAN_VAULT_PATH",
    "daily_notes_folder": "DAILY_NOTES_FOLDER",
    "github_token": "GITHUB_TOKEN",
    "github_username": "GITHUB_USERNAME",
    "github_client_id": "GITHUB_CLIENT_ID",
    "github_client_secret": "GITHUB_CLIENT_SECRET",
    "github_webhook_secret": "GITHUB_WEBHOOK_SECRET",
    "google_client_id": "GOOGLE_CLIENT_ID",
    "google_client_secret": "GOOGLE_CLIENT_SECRET",
    "google_redirect_uri": "GOOGLE_REDIRECT_URI",
    "openai_api_key": "OPENAI_API_KEY",
    "openai_base_url": "OPENAI_BASE_URL",
    "llm_model": "LLM_MODEL",
    "embedding_model": "EMBEDDING_MODEL",
    "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
    "telegram_allowed_user_id": "TELEGRAM_ALLOWED_USER_ID",
    "telegram_webhook_secret": "TELEGRAM_WEBHOOK_SECRET",
    "secret_key": "SECRET_KEY",
    "app_env": "APP_ENV",
    "ai_service_enabled": "AI_SERVICE_ENABLED",
}

# Keys where an empty string is a deliberate "clear" request (e.g. the GitHub
# disconnect flow sends ``github_token: ""`` to wipe the stored token). For
# every other key an empty value means "not provided": writing it into .env
# would silently clobber a working config with "" (#1304). Secret fields are
# never returned by GET /config, so clients can't distinguish "clear" from
# "field left blank" for them — they must stay non-clearable.
CLEARABLE_KEYS = {"github_token", "github_username", "daily_notes_folder"}

PUBLIC_KEYS = {
    "gemini_api_key": False,
    "obsidian_vault_path": True,
    "daily_notes_folder": True,
    "github_token": False,
    "github_username": True,
    "github_client_id": False,
    "github_client_secret": False,
    "github_webhook_secret": False,
    "google_client_id": False,
    "google_client_secret": False,
    "google_redirect_uri": True,
    "openai_api_key": False,
    "openai_base_url": True,
    "llm_model": True,
    "embedding_model": True,
    "telegram_bot_token": False,
    "telegram_allowed_user_id": False,
    "telegram_webhook_secret": False,
    "secret_key": False,
    "app_env": True,
    "ai_service_enabled": True,
}


# Values shipped in .env.example (or used as placeholders) that must count as
# "not configured" — otherwise a manual ``cp .env.example .env`` would trip
# the setup-completed guard forever.
_PLACEHOLDER_VALUES = frozenset({"", "your_gemini_api_key_here", "change_this_to_a_random_secret_key"})


def _configured(value: str | None) -> bool:
    """True when a value is present and not a shipped placeholder."""
    if not value:
        return False
    return value.strip() not in _PLACEHOLDER_VALUES


class ConfigResponse(BaseModel):
    gemini_api_key: str | None = None
    obsidian_vault_path: str | None = None
    daily_notes_folder: str | None = None
    github_username: str | None = None
    github_token: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    openai_base_url: str | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    app_env: str | None = None
    configured_keys: list[str]


class ConfigUpdate(BaseModel):
    gemini_api_key: str | None = None
    obsidian_vault_path: str | None = None
    daily_notes_folder: str | None = None
    github_token: str | None = None
    github_username: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_webhook_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    telegram_bot_token: str | None = None
    telegram_allowed_user_id: str | None = None
    telegram_webhook_secret: str | None = None
    secret_key: str | None = None


@router.get("", response_model=ConfigResponse, dependencies=[Depends(get_current_user)])
def get_config():
    env_vars = read_env()
    configured = []
    response_data = {}

    for short_key, env_key in CONFIG_KEYS.items():
        value = env_vars.get(env_key, "")
        is_public = PUBLIC_KEYS.get(short_key, False)

        if _configured(value):
            configured.append(short_key)

        if is_public:
            response_data[short_key] = value if value else None
        else:
            response_data[short_key] = None

    return ConfigResponse(**response_data, configured_keys=configured)


@router.post("", dependencies=[Depends(get_current_user)])
def update_config(update: ConfigUpdate):
    env_vars = read_env()

    update_data = update.model_dump(exclude_none=True)

    # Empty values mean "not provided" for non-clearable keys — strip them so
    # an empty string can never clobber a working .env entry or an in-memory
    # setting (pydantic reads "" as set). Only CLEARABLE_KEYS accept "" as a
    # deliberate clear (#1304).
    update_data = {k: v for k, v in update_data.items() if k in CLEARABLE_KEYS or (v or "").strip()}

    # Detect vault path change — Docker bind mounts are immutable, so changing
    # OBSIDIAN_VAULT_PATH requires recreating the worker/api containers for the
    # new path to take effect (#784).
    old_vault = env_vars.get("OBSIDIAN_VAULT_PATH", "")
    new_vault = update_data.get("obsidian_vault_path", "")
    vault_changed = bool(new_vault) and new_vault != old_vault

    for short_key, env_key in CONFIG_KEYS.items():
        if short_key in update_data:
            value = update_data[short_key]
            if value is not None:
                try:
                    env_vars[env_key] = validate_env_value(env_key, value)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid value for '{short_key}': {exc}") from exc
                # Keep the in-memory update below in sync with the persisted
                # (possibly normalized) value.
                update_data[short_key] = env_vars[env_key]

    try:
        write_env(env_vars)
    except ValueError as exc:
        # A key already on disk can fail the universal safety check (#1312) —
        # fail closed rather than round-trip a poisoned value.
        raise HTTPException(status_code=400, detail=f"Refusing to persist .env: {exc}") from exc

    # Update in-memory settings so services see the new values immediately
    for short_key, value in update_data.items():
        if value is not None and hasattr(settings, short_key):
            setattr(settings, short_key, value)

    result: dict = {"status": "ok", "message": "Configuration updated."}
    if vault_changed:
        result["requires_restart"] = True
        result["restart_reason"] = (
            "Vault path changed. Docker bind mounts are immutable — "
            "recreate the stack for the new path to take effect: "
            "docker compose up -d --force-recreate worker api"
        )
    # AI provider settings are consumed by the ai-service process (not the API):
    # flag a restart so the panel can prompt the user (#42 pattern).
    ai_keys = {"openai_api_key", "openai_base_url", "llm_model", "embedding_model", "gemini_api_key"}
    if ai_keys & update_data.keys():
        result["requires_restart"] = True
        result["restart_reason"] = (
            "Cambios en la IA: reinicia el servicio de IA para aplicarlos "
            "(docker compose restart ai-service o el botón de Servicios)."
        )
    return result


@router.get("/keys", dependencies=[Depends(get_current_user)])
def get_available_keys():
    return {
        "keys": [
            {
                "key": short_key,
                "env_key": env_key,
                "public": PUBLIC_KEYS.get(short_key, False),
                "description": get_key_description(short_key),
            }
            for short_key, env_key in CONFIG_KEYS.items()
        ]
    }


def get_key_description(key: str) -> str:
    descriptions = {
        "gemini_api_key": "API key for Google Gemini AI",
        "obsidian_vault_path": "Path to your Obsidian vault (supports ~ for home-relative, expanded by `joidy up`)",
        "daily_notes_folder": "Relative folder inside your vault for daily notes",
        "github_token": "GitHub Personal Access Token",
        "github_username": "GitHub username",
        "github_client_id": "GitHub OAuth App client ID",
        "github_client_secret": "GitHub OAuth App client secret",
        "github_webhook_secret": "Shared secret GitHub signs webhook deliveries with (X-Hub-Signature-256)",
        "telegram_bot_token": "Telegram Bot API token",
        "telegram_allowed_user_id": "Your Telegram user ID",
        "telegram_webhook_secret": "Secret token Telegram sends on each webhook call",
        "secret_key": "Session signing secret key",
        "app_env": "Application environment (development/production)",
    }
    return descriptions.get(key, "")


class GamificationConfig(BaseModel):
    xp_table: dict
    plant_stages: list[dict]
    streak_milestones: list[int]


@router.get("/gamification", response_model=GamificationConfig, dependencies=[Depends(get_current_user)])
def get_gamification_config():
    from services.gamification_engine import (
        PLANT_STAGES,
        STREAK_MILESTONES,
        get_xp_table,
    )

    xp_table = get_xp_table()
    return GamificationConfig(
        xp_table=xp_table,
        plant_stages=[{"stage": i, "name": name, "xp_required": xp} for i, (xp, name) in enumerate(PLANT_STAGES)],
        streak_milestones=STREAK_MILESTONES,
    )


class SetupRequest(BaseModel):
    auth_password: str
    obsidian_vault_path: str | None = None


# Password policy for first-boot setup (#1284). The master password is the
# single credential protecting the whole dataset, so a weak one defeats the
# entire auth model. Dependency-free denylist: the most common passwords and
# their trivially extended (≥12 char) variants.
_SETUP_MIN_PASSWORD_LENGTH = 12

_COMMON_SETUP_PASSWORDS = frozenset(
    {
        # Classic top-passwords lists (most are < 12 chars and already blocked
        # by the length rule, but the denylist must also catch them after a
        # suffix/prefix is appended).
        "password",
        "123456",
        "123456789",
        "12345678",
        "1234567890",
        "12345",
        "1234567",
        "1234",
        "qwerty",
        "abc123",
        "111111",
        "football",
        "monkey",
        "letmein",
        "dragon",
        "baseball",
        "iloveyou",
        "trustno1",
        "sunshine",
        "master",
        "welcome",
        "shadow",
        "ashley",
        "michael",
        "ninja",
        "mustang",
        "password1",
        "123123",
        "admin",
        "admin123",
        "superman",
        "batman",
        "login",
        "princess",
        "qwerty123",
        "qwertyuiop",
        "starwars",
        "whatever",
        "freedom",
        "hello",
        "charlie",
        "donald",
        "123qwe",
        "123321",
        "654321",
        "555555",
        "7777777",
        "888888",
        "jordan",
        "zxcvbnm",
        "asdfgh",
        "hunter",
        "buster",
        "soccer",
        "harley",
        "ranger",
        "jessica",
        "pepper",
        "daniel",
        "banana",
        "hockey",
        "killer",
        "george",
        "computer",
        "michelle",
        "passw0rd",
        "p@ssw0rd",
        "changeme",
        "secret",
        "letmein123",
        # Common ≥12-character variants that would pass the length rule alone.
        "password123",
        "password1234",
        "password12345",
        "qwerty123456",
        "qwerty1234567",
        "administrator",
        "administrator1",
        "1q2w3e4r5t",
        "1q2w3e4r5t6y",
        "123456789012",
        "1234567890123",
        "12345678901234",
        "1234567891011",
        "iloveyou123",
        "iloveyou1234",
        "welcome123",
        "welcome1234",
        "changeme123",
        "changeme1234",
        "letmein1234",
        "abc123456789",
        "abcd12345678",
        "supersecret",
        "supersecret1",
        "secret1234",
        "joidyjoidy12",
        "admin123456",
        "admin1234567",
        "root12345678",
        "test12345678",
        "user12345678",
        "guest1234567",
        "default12345",
        "trustno11234",
    }
)

# Headers that make the reported client address untrusted for the setup
# lockdown (#1292). Uvicorn runs with ``--proxy-headers
# --forwarded-allow-ips='*'``, so ``request.client`` reflects
# ``X-Forwarded-For`` whenever the header is present — and any remote caller
# can set it to ``127.0.0.1``. Nothing in the default deployment proxies this
# endpoint, so a forwarding header here is either a spoof attempt or an
# unsupported proxy path; both are refused.
_UNTRUSTED_FORWARD_HEADERS = ("x-forwarded-for", "x-real-ip", "forwarded")


def _default_gateway_ips() -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Default gateway IPs of this process's network namespace.

    Inside a container, traffic entering through a published port from the
    Docker/Podman *host* arrives with the bridge (or slirp/pasta) gateway as
    the source address — the gateway IS the host, so it counts as a local
    client. Remote clients keep their own source IP and fail the check.
    """
    gateways: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    try:
        with open("/proc/net/route") as f:
            for line in f.read().splitlines()[1:]:
                fields = line.split()
                # Iface Destination Gateway Flags ... — destination 0.0.0.0 is
                # the default route; gateway is little-endian hex IPv4.
                if len(fields) >= 3 and fields[1] == "00000000":
                    try:
                        gateways.add(ipaddress.IPv4Address(bytes.fromhex(fields[2])[::-1]))
                    except ValueError:
                        continue
    except OSError:
        pass
    try:
        with open("/proc/net/ipv6_route") as f:
            for line in f.read().splitlines():
                fields = line.split()
                # dest(32hex) prefixlen src(32hex) srclen nexthop(32hex) ...
                if len(fields) >= 5 and fields[1] == "00" and int(fields[0], 16) == 0:
                    try:
                        nexthop = int(fields[4], 16)
                    except ValueError:
                        continue
                    if nexthop:
                        gateways.add(ipaddress.IPv6Address(nexthop))
    except OSError:
        pass
    return gateways


def _is_local_setup_client(request: Request) -> bool:
    """True only when the request peer is the machine hosting Joidy.

    Accepts loopback (bare-metal installs, ``docker exec``, SSH tunnels) and
    the container's default gateway (host-originated traffic through published
    ports). Everything else — remote LAN/WAN clients, forged or proxied
    requests — is refused to close the first-boot race (#1292).
    """
    if any(header in request.headers for header in _UNTRUSTED_FORWARD_HEADERS):
        return False
    if request.client is None:
        return False
    try:
        ip = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)  # ::ffff:127.0.0.1 → 127.0.0.1
    if mapped is not None:
        ip = mapped
    if ip.is_loopback:
        return True
    return ip in _default_gateway_ips()


def _validate_setup_password(password: str) -> None:
    """Enforce the first-boot password policy (#1284)."""
    if not password or len(password) < _SETUP_MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {_SETUP_MIN_PASSWORD_LENGTH} characters long",
        )
    if password.lower() in _COMMON_SETUP_PASSWORDS or len(set(password)) == 1:
        raise HTTPException(
            status_code=400,
            detail="Password is too common or predictable — choose a stronger passphrase",
        )


def _setup_is_complete(env_vars: dict) -> bool:
    """True when ANY part of the auth config already exists (#1292).

    Checking both keys used to be required to refuse re-setup, which let a
    partial-config state (e.g. only SECRET_KEY present) allow re-setup to
    overwrite AUTH_PASSWORD — a password takeover. Persisted file values and
    process env (settings) are both consulted; placeholders don't count.
    """
    return any(
        _configured(value)
        for value in (
            env_vars.get("AUTH_PASSWORD"),
            env_vars.get("SECRET_KEY"),
            settings.auth_password,
            settings.secret_key,
        )
    )


@router.get("/setup-status")
def setup_status():
    env_vars = read_env()
    # needs_setup stays False only once BOTH keys are genuinely configured;
    # placeholder values from .env.example don't count as configured.
    needs_setup = not (_configured(env_vars.get("AUTH_PASSWORD")) and _configured(env_vars.get("SECRET_KEY")))
    # Only reveal whether setup is needed — no sensitive information
    return {"needs_setup": needs_setup}


@router.post("/setup")
def perform_setup(request: Request, req: SetupRequest):
    # First-boot endpoint — restricted to the machine hosting the service
    # (#1292). Remote clients racing a fresh deployment to claim the instance
    # get a 403, as do requests carrying forwarding headers (the reported
    # client would be spoofable).
    if not _is_local_setup_client(request):
        raise HTTPException(
            status_code=403,
            detail="Setup can only be performed from the machine hosting Joidy.",
        )

    env_vars = read_env()

    # Reject when setup is even partially done — prevents re-setup and
    # password-takeover attacks (#1292).
    if _setup_is_complete(env_vars):
        raise HTTPException(
            status_code=403,
            detail=(
                "Setup already completed. Use the settings page to change "
                "configuration, or remove AUTH_PASSWORD/SECRET_KEY from .env "
                "to re-run setup."
            ),
        )

    _validate_setup_password(req.auth_password)

    # Validate free-text input before it touches .env (#1312): a crafted vault
    # path used to persist verbatim — newlines forged extra KEY= lines and
    # $(...) executed on the next `make` invocation that sourced the file.
    vault_path: str | None = None
    if req.obsidian_vault_path:
        try:
            vault_path = validate_env_value("OBSIDIAN_VAULT_PATH", req.obsidian_vault_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid obsidian_vault_path: {exc}") from exc

    env_vars["AUTH_PASSWORD"] = hash_password(req.auth_password)
    if vault_path:
        env_vars["OBSIDIAN_VAULT_PATH"] = vault_path

    # Always mint a fresh SECRET_KEY on successful setup (#1292): rotating it
    # invalidates any tokens signed before setup completed (e.g. under a
    # placeholder secret), and a fresh key lands in the file even when .env
    # already carried a placeholder entry.
    env_vars["SECRET_KEY"] = secrets.token_urlsafe(32)

    if not env_vars.get("INTERNAL_API_TOKEN"):
        env_vars["INTERNAL_API_TOKEN"] = secrets.token_urlsafe(32)

    try:
        write_env(env_vars)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Refusing to persist .env: {exc}") from exc

    # Reload settings in memory (best-effort — the authoritative source is
    # now the .env file, which every worker reads via get_persisted()).
    settings.auth_password = env_vars["AUTH_PASSWORD"]
    settings.secret_key = env_vars["SECRET_KEY"]
    settings.internal_api_token = env_vars["INTERNAL_API_TOKEN"]
    if vault_path:
        os.environ["OBSIDIAN_VAULT_PATH"] = vault_path
        settings.obsidian_vault_path = vault_path

    return {
        "status": "ok",
        "message": "Setup completed",
        "requires_restart": False,
    }
