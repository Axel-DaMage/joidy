"""Regression tests for #1282 — dev-mode auth bypass is loopback-only.

Without ``AUTH_PASSWORD`` the API used to accept unauthenticated requests
from ANY peer, so ``make dev`` publishing ``0.0.0.0`` exposed full
read/write access to the LAN. The bypass now applies to loopback peers
(127.0.0.0/8, ::1) only; every other client must present a valid token.

The TestClient default peer (``"testclient"``) is not an IP literal and
fails closed — tests always pass an explicit ``client=(host, port)``.
"""

import json

import pytest
from config import settings
from database import get_db
from fastapi.testclient import TestClient
from main import app
from services.auth_service import _is_loopback, create_access_token
from starlette.websockets import WebSocketDisconnect

LAN_PEER = ("192.168.1.50", 4001)
PUBLIC_PEER = ("203.0.113.10", 4002)


@pytest.fixture
def real_auth_client(db_session):
    """Factory of TestClients bound to an arbitrary peer address.

    Only ``get_db`` is overridden — requests exercise the REAL
    ``get_current_user`` dependency (unlike the shared ``client`` fixture).
    """

    def override_get_db():
        yield db_session

    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    try:

        def _make(host: str, port: int = 1234) -> TestClient:
            return TestClient(app, client=(host, port))

        yield _make
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


@pytest.fixture
def dev_no_password(monkeypatch):
    """Development environment with authentication disabled."""
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-loopback-tests")
    return settings


class TestIsLoopback:
    """_is_loopback must be strict: only literal loopback IPs pass."""

    @pytest.mark.parametrize(
        "host",
        ["127.0.0.1", "127.0.0.2", "127.255.255.254", "::1", "::ffff:127.0.0.1"],
    )
    def test_loopback_addresses_accepted(self, host):
        assert _is_loopback(host) is True

    @pytest.mark.parametrize(
        "host",
        [
            "192.168.1.10",
            "10.0.0.8",
            "172.16.0.5",
            "203.0.113.7",
            "fe80::1",
            "::ffff:10.0.0.5",  # IPv4-mapped non-loopback must not smuggle in
            "testclient",  # TestClient default peer is a name, not an IP
            "localhost",  # hostnames are not IPs — fail closed
            "",
            None,
        ],
    )
    def test_non_loopback_fails_closed(self, host):
        assert _is_loopback(host) is False


class TestHttpBypassLoopbackOnly:
    def test_loopback_ipv4_accepted_without_token(self, real_auth_client, dev_no_password):
        resp = real_auth_client("127.0.0.1").get("/notes/")
        assert resp.status_code == 200

    def test_loopback_ipv6_accepted_without_token(self, real_auth_client, dev_no_password):
        resp = real_auth_client("::1").get("/notes/")
        assert resp.status_code == 200

    def test_lan_client_rejected_without_token(self, real_auth_client, dev_no_password):
        resp = real_auth_client(LAN_PEER[0]).get("/notes/")
        assert resp.status_code == 401

    def test_public_client_rejected_without_token(self, real_auth_client, dev_no_password):
        resp = real_auth_client(PUBLIC_PEER[0]).get("/notes/")
        assert resp.status_code == 401

    def test_non_loopback_with_valid_token_allowed(self, real_auth_client, dev_no_password):
        """Non-loopback peers behave like an authenticated deployment:
        a valid Bearer token is still accepted."""
        token = create_access_token(1)
        resp = real_auth_client(PUBLIC_PEER[0]).get("/notes/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_non_loopback_with_invalid_token_rejected(self, real_auth_client, dev_no_password):
        resp = real_auth_client(PUBLIC_PEER[0]).get("/notes/", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    def test_production_still_rejects_loopback(self, real_auth_client, monkeypatch):
        """The production fail-closed guard is unchanged: no AUTH_PASSWORD
        in production rejects even loopback callers."""
        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "auth_password", "")
        resp = real_auth_client("127.0.0.1").get("/notes/")
        assert resp.status_code == 401
        assert "Authentication not configured" in resp.json()["detail"]


class TestWebSocketLoopbackOnly:
    def test_ws_non_loopback_dev_rejected_without_token(self, dev_no_password):
        ws_client = TestClient(app, client=PUBLIC_PEER)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with ws_client.websocket_connect("/ws"):
                pass
        assert exc_info.value.code == 4001

    def test_ws_non_loopback_dev_accepts_valid_token(self, dev_no_password):
        token = create_access_token(1)
        ws_client = TestClient(app, client=PUBLIC_PEER)
        with ws_client.websocket_connect(f"/ws?token={token}") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            assert websocket.receive_json() == {"type": "pong"}

    def test_ws_loopback_dev_still_bypasses(self, client, dev_no_password):
        """The shared ``client`` fixture presents a loopback peer — the dev
        bypass must keep working for local development."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text(json.dumps({"type": "ping"}))
            assert websocket.receive_json() == {"type": "pong"}


class TestWebhookLoopbackOnly:
    def test_webhook_non_loopback_dev_requires_auth(self, real_auth_client, dev_no_password, monkeypatch):
        """No webhook secret and no AUTH_PASSWORD: only loopback bypasses —
        a LAN peer falls through to JWT auth and gets 401 (#1282)."""
        monkeypatch.setattr(settings, "obsidian_webhook_secret", "")
        resp = real_auth_client(PUBLIC_PEER[0]).post(
            "/webhook/obsidian",
            json={"event": "create", "path": "/vault/lan-peer.md", "content": "x"},
        )
        assert resp.status_code == 401

    def test_webhook_non_loopback_accepts_bearer(self, real_auth_client, dev_no_password, monkeypatch):
        monkeypatch.setattr(settings, "obsidian_webhook_secret", "")
        token = create_access_token(1)
        resp = real_auth_client(PUBLIC_PEER[0]).post(
            "/webhook/obsidian",
            json={"event": "create", "path": "/vault/lan-token.md", "content": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
