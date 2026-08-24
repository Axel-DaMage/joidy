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
from unittest.mock import AsyncMock, MagicMock

import pytest
from config import settings
from fastapi.testclient import TestClient
from routers.websocket import ConnectionManager
from services.auth_service import create_access_token
from starlette.websockets import WebSocketDisconnect

# --- Connection (dev mode, auth bypassed) ------------------------------------


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
    """An invalid token is rejected with 4001."""
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")
    monkeypatch.setattr(settings, "app_env", "development")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?token=invalid-token"):
            pass

    assert exc_info.value.code == 4001


def test_ws_connect_with_valid_token(client: TestClient, monkeypatch):
    """A valid JWT token allows the connection and ping/pong works."""
    monkeypatch.setattr(settings, "auth_password", "test-secret")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-32bytes-long-aaaa")
    monkeypatch.setattr(settings, "app_env", "development")

    token = create_access_token(user_id=1)
    with client.websocket_connect(f"/ws?token={token}") as websocket:
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
