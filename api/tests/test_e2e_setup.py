"""E2E tests for POST /config/setup lockdown (#1284, #1292).

Covers the first-boot hardening:
- loopback/gateway-only access — remote and forwarded (spoofable) clients get 403
- "either key present" = setup completed (partial-config can't be taken over)
- .env.example placeholder values don't count as configured
- password policy: min 12 chars, common-password denylist, single-char repeats
- SECRET_KEY is always minted fresh on success (rotates any placeholder)
"""

import ipaddress
import os

import pytest
import routers.config as config_router
from fastapi.testclient import TestClient
from main import app
from services.env_file import read_env

GOOD_PASSPHRASE = "correct-horse-battery-staple-92"


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch):
    """Neutralize process-global auth state for this file's tests.

    ``perform_setup`` mutates ``settings.auth_password``/``settings.secret_key``
    on success; without this, values would leak into other tests (and the
    setup-completed guard would see them).
    """
    monkeypatch.setattr(config_router.settings, "auth_password", "")
    monkeypatch.setattr(config_router.settings, "secret_key", "")
    # perform_setup also mutates settings.obsidian_vault_path and
    # os.environ["OBSIDIAN_VAULT_PATH"] — snapshot both so vault confinement
    # (#1314) keeps seeing the suite root for the rest of the worker.
    monkeypatch.setattr(config_router.settings, "obsidian_vault_path", config_router.settings.obsidian_vault_path)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", os.environ.get("OBSIDIAN_VAULT_PATH", "/vault"))


def _client(host: str = "127.0.0.1", port: int = 40000) -> TestClient:
    """TestClient whose ASGI ``scope['client']`` simulates a given TCP peer."""
    return TestClient(app, client=(host, port))


# ---------------------------------------------------------------------------
# #1292 — loopback / forwarding restrictions
# ---------------------------------------------------------------------------


def test_setup_rejects_non_loopback_client():
    with _client("203.0.113.10") as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 403


def test_setup_rejects_lan_client():
    with _client("192.168.1.50") as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 403


def test_setup_rejects_forwarded_header_spoof():
    """A remote client sending X-Forwarded-For: 127.0.0.1 must not pass.

    uvicorn runs with --forwarded-allow-ips='*', so the reported client would
    be replaced by the forged header — the endpoint refuses forwarded headers
    outright.
    """
    with _client("203.0.113.10") as c:
        resp = c.post(
            "/config/setup",
            json={"auth_password": GOOD_PASSPHRASE},
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
    assert resp.status_code == 403


def test_setup_rejects_forwarded_header_even_from_loopback():
    with _client("127.0.0.1") as c:
        resp = c.post(
            "/config/setup",
            json={"auth_password": GOOD_PASSPHRASE},
            headers={"X-Forwarded-For": "10.0.0.5"},
        )
    assert resp.status_code == 403


def test_setup_rejects_non_ip_client():
    with _client("testclient") as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 403


def test_setup_accepts_default_gateway_client(monkeypatch):
    """Host-originated traffic through a published container port arrives with
    the bridge gateway as source — it must count as a local client."""
    fake_gateways = {ipaddress.ip_address("172.18.0.1")}
    monkeypatch.setattr(config_router, "_default_gateway_ips", lambda: fake_gateways)
    with _client("172.18.0.1") as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# #1292 — "either key present" setup-completed guard
# ---------------------------------------------------------------------------


def test_setup_rejects_when_only_secret_key(persisted_env):
    persisted_env.write_text("SECRET_KEY=a-real-secret-key-value\n")
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 403
    assert "already completed" in resp.json()["detail"]


def test_setup_rejects_when_only_auth_password(persisted_env):
    persisted_env.write_text("AUTH_PASSWORD=$2b$04$somebcryptvalue\n")
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 403


def test_setup_rejects_when_secret_key_in_process_env(persisted_env, monkeypatch):
    """SECRET_KEY provided via the process environment (not the .env file)
    must also count as configured — pydantic settings precedence means a file
    value couldn't even override it."""
    monkeypatch.setattr(config_router.settings, "secret_key", "env-var-secret")
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 403


def test_setup_runs_when_secret_key_is_placeholder(persisted_env):
    """A manual ``cp .env.example .env`` leaves the shipped placeholder — it
    must not count as configured or setup could never run."""
    persisted_env.write_text("SECRET_KEY=change_this_to_a_random_secret_key\n")
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# #1284 — password policy
# ---------------------------------------------------------------------------


def test_setup_short_password_400():
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": "1234"})
    assert resp.status_code == 400


def test_setup_empty_password_400():
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": ""})
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "password",
    ["password1234", "PASSWORD1234", "1q2w3e4r5t6y", "administrator", "aaaaaaaaaaaa"],
)
def test_setup_common_password_400(password):
    """Denylist entries (case-insensitive) and single-char repeats are rejected
    even at ≥12 chars."""
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": password})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Successful setup — persistence + secret rotation
# ---------------------------------------------------------------------------


def test_setup_success_200_and_persists(persisted_env):
    with _client() as c:
        resp = c.post(
            "/config/setup",
            json={"auth_password": GOOD_PASSPHRASE, "obsidian_vault_path": "/tmp/vault"},
        )
    assert resp.status_code == 200
    env = read_env()
    assert env["AUTH_PASSWORD"].startswith("$2b$")  # bcrypt hash, not plaintext
    assert env["OBSIDIAN_VAULT_PATH"] == "/tmp/vault"
    assert env["SECRET_KEY"] and env["SECRET_KEY"] != "change_this_to_a_random_secret_key"
    assert len(env["SECRET_KEY"]) >= 32
    # In-memory settings follow the persisted values.
    assert config_router.settings.secret_key == env["SECRET_KEY"]
    assert config_router.settings.auth_password == env["AUTH_PASSWORD"]


def test_setup_rotates_placeholder_secret_key(persisted_env):
    """Rotation on success: tokens signed under the shipped placeholder (or any
    pre-setup secret) are invalidated by the fresh key."""
    persisted_env.write_text("SECRET_KEY=change_this_to_a_random_secret_key\n")
    with _client() as c:
        resp = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
    assert resp.status_code == 200
    env = read_env()
    assert env["SECRET_KEY"] != "change_this_to_a_random_secret_key"


def test_setup_second_run_forbidden(persisted_env):
    """Once setup succeeds, a second run must 403 (full-config now exists)."""
    with _client() as c:
        first = c.post("/config/setup", json={"auth_password": GOOD_PASSPHRASE})
        assert first.status_code == 200
        second = c.post("/config/setup", json={"auth_password": "another-strong-passphrase-77"})
        assert second.status_code == 403


# ---------------------------------------------------------------------------
# setup-status — placeholder awareness
# ---------------------------------------------------------------------------


def test_setup_status_placeholder_not_configured(persisted_env):
    persisted_env.write_text("SECRET_KEY=change_this_to_a_random_secret_key\n")
    with _client() as c:
        resp = c.get("/config/setup-status")
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is True


def test_setup_status_full_config(persisted_env):
    persisted_env.write_text("AUTH_PASSWORD=$2b$04$x\nSECRET_KEY=real-secret\n")
    with _client() as c:
        resp = c.get("/config/setup-status")
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is False
