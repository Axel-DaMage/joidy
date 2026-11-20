"""Tests for the /ws WebSocket endpoint and ConnectionManager (#13).

Covers:
- WebSocket connection in development mode (auth bypassed).
- WebSocket connection with a valid JWT token when auth is configured.
- WebSocket rejection when no token is provided and auth is configured.
- Ping/pong message handling.
- ConnectionManager.broadcast delivering messages to connected clients.
"""

import asyncio
import json
import logging
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
from config import settings
from fastapi.testclient import TestClient
from main import app
from routers.websocket import ConnectionManager
from services.auth_service import create_access_token
from starlette.websockets import WebSocketDisconnect

# --- Connection (dev mode, auth bypassed) ------------------------------------
#
# The shared ``client`` fixture presents a loopback peer (127.0.0.1) — the
# #1282 dev bypass is loopback-only, so these tests still exercise it.


def test_ws_connect_dev_mode(client: TestClient, monkeypatch):
    """In development without AUTH_PASSWORD, the /ws endpoint accepts connections."""
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "app_env", "development")

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(json.dumps({"type": "ping"}))
        data = websocket.receive_json()
        assert data == {"type": "pong"}


def test_ws_ping_pong(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "app_env", "development")

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}


def test_ws_ignores_non_json(client: TestClient, monkeypatch):
    """Malformed (non-JSON) messages are silently ignored, not crashing the socket."""
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "app_env", "development")

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("not-json-at-all")
        # A subsequent valid ping should still work.
        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}


# --- Authentication ----------------------------------------------------------


def test_ws_rejected_without_token(client: TestClient, monkeypatch):
    """When AUTH_PASSWORD is set, connecting without a token is rejected (4001)."""
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "app_env", "development")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            pass

    assert exc_info.value.code == 4001


def test_ws_rejected_with_invalid_token(client: TestClient, monkeypatch):
    """An invalid token offered via Sec-WebSocket-Protocol is rejected (4001)."""
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")
    monkeypatch.setattr(settings, "app_env", "development")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws", subprotocols=["bearer", "invalid-token"]):
            pass

    assert exc_info.value.code == 4001


def test_ws_connect_with_valid_token(client: TestClient, monkeypatch):
    """A valid JWT offered via Sec-WebSocket-Protocol connects; ping/pong works."""
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-32bytes-long-aaaa")
    monkeypatch.setattr(settings, "app_env", "development")

    token = create_access_token(user_id=1)
    with client.websocket_connect("/ws", subprotocols=["bearer", token]) as websocket:
        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}


def test_ws_query_param_token_no_longer_authenticates(client: TestClient, monkeypatch):
    """A *valid* JWT in ?token= must NOT authenticate (#1285).

    Query-string credentials leak into proxy access logs and browser history;
    the only accepted transport is the Sec-WebSocket-Protocol handshake header.
    """
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-32bytes-long-aaaa")
    monkeypatch.setattr(settings, "app_env", "development")

    token = create_access_token(user_id=1)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws?token={token}"):
            pass

    assert exc_info.value.code == 4001


def test_ws_rejects_refresh_token(client: TestClient, monkeypatch):
    """A refresh token (typ=refresh) cannot open a WS connection (#1285)."""
    from services.auth_service import create_refresh_token

    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-32bytes-long-aaaa")
    monkeypatch.setattr(settings, "app_env", "development")

    refresh = create_refresh_token(user_id=1)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws", subprotocols=["bearer", refresh]):
            pass

    assert exc_info.value.code == 4001


def test_ws_token_only_subprotocol_authenticates(client: TestClient, monkeypatch):
    """Offering the JWT alone (without the 'bearer' marker) still works —
    the server simply answers with no negotiated subprotocol."""
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-32bytes-long-aaaa")
    monkeypatch.setattr(settings, "app_env", "development")

    token = create_access_token(user_id=1)
    with client.websocket_connect("/ws", subprotocols=[token]) as websocket:
        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}


# --- Non-loopback dev bypass restrictions (#1282) -----------------------------


def test_ws_rejected_non_loopback_dev_mode(monkeypatch):
    """#1282: dev bypass is loopback-only — a LAN peer without token → 4001."""
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "app_env", "development")

    remote = TestClient(app, client=("203.0.113.9", 4321))
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with remote.websocket_connect("/ws"):
            pass

    assert exc_info.value.code == 4001


def test_ws_non_loopback_dev_accepts_valid_token(monkeypatch):
    """A non-loopback peer is treated like an authenticated deployment:
    a valid Bearer token still connects (#1282)."""
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-32bytes-long-aaaa")
    monkeypatch.setattr(settings, "app_env", "development")

    token = create_access_token(user_id=1)
    remote = TestClient(app, client=("203.0.113.9", 4321))
    with remote.websocket_connect("/ws", subprotocols=["bearer", token]) as websocket:
        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}


# --- ConnectionManager.broadcast ---------------------------------------------


def test_manager_broadcast_delivers_to_all():
    """broadcast() sends the message to every active connection."""

    async def _run():
        manager = ConnectionManager()
        ws_a = MagicMock()
        ws_a.send_json = AsyncMock()
        ws_b = MagicMock()
        ws_b.send_json = AsyncMock()
        manager.active_connections = {ws_a, ws_b}

        await manager.broadcast({"type": "note_created", "note_id": 1, "title": "Hi"})

        ws_a.send_json.assert_awaited_once_with({"type": "note_created", "note_id": 1, "title": "Hi"})
        ws_b.send_json.assert_awaited_once_with({"type": "note_created", "note_id": 1, "title": "Hi"})

    asyncio.run(_run())


def test_manager_broadcast_no_connections_is_noop():
    """broadcast() with no active connections does nothing."""

    async def _run():
        manager = ConnectionManager()
        await manager.broadcast({"type": "test"})  # must not raise

    asyncio.run(_run())


def test_manager_broadcast_removes_failed_connections():
    """A connection that raises on send is removed from the active set."""

    async def _run():
        manager = ConnectionManager()
        good_ws = MagicMock()
        good_ws.send_json = AsyncMock()
        bad_ws = MagicMock()
        bad_ws.send_json = AsyncMock(side_effect=RuntimeError("disconnected"))
        manager.active_connections = {good_ws, bad_ws}

        await manager.broadcast({"type": "test"})

        assert good_ws in manager.active_connections
        assert bad_ws not in manager.active_connections

    asyncio.run(_run())


def test_manager_connect_and_disconnect():
    """connect() adds and accept()s; disconnect() removes from the active set."""

    async def _run():
        manager = ConnectionManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        await manager.connect(ws)
        assert ws in manager.active_connections
        ws.accept.assert_awaited_once()

        manager.disconnect(ws)
        assert ws not in manager.active_connections

    asyncio.run(_run())


# --- _schedule_broadcast (#992) ----------------------------------------------


def test_schedule_broadcast_inside_running_loop():
    """Called from async context, the coroutine is scheduled directly."""
    from routers import websocket

    ran = []

    async def _run():
        async def notify():
            ran.append(True)

        websocket._schedule_broadcast(notify())
        await asyncio.sleep(0)
        assert ran

    asyncio.run(_run())


def test_schedule_broadcast_from_thread_reaches_main_loop():
    """Called from a thread with no loop (sync endpoint), the coroutine still
    runs on the captured main loop — previously it was silently dropped."""

    from routers import websocket

    ran = []

    async def _main():
        websocket.set_main_loop(asyncio.get_running_loop())

        async def notify():
            ran.append(True)

        worker = threading.Thread(target=websocket._schedule_broadcast, args=(notify(),))
        worker.start()
        worker.join()

        for _ in range(100):
            if ran:
                break
            await asyncio.sleep(0.01)
        assert ran

    try:
        asyncio.run(_main())
    finally:
        websocket.set_main_loop(None)


def test_schedule_broadcast_without_any_loop_warns(caplog):
    """No running loop and no captured loop: coroutine closed, warning logged."""

    from routers import websocket

    websocket.set_main_loop(None)

    async def notify():
        pass

    with caplog.at_level(logging.WARNING, logger="routers.websocket"):
        websocket._schedule_broadcast(notify())

    assert "Broadcast dropped" in caplog.text
