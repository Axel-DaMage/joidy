"""
WebSocket endpoints for real-time updates.
"""

import asyncio
import json
import logging

from config import settings
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.auth_service import verify_token, _effective_auth_password

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Main event loop, captured at startup so broadcast_* helpers can schedule
# coroutines from sync endpoints running in the threadpool (#992).
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop):
    """Record the app's running event loop for cross-thread broadcasts."""
    global _main_loop
    _main_loop = loop


def _schedule_broadcast(coro):
    """Schedule a broadcast coroutine from sync or async contexts.

    Async endpoints get a normal create_task. Sync `def` endpoints run in the
    anyio threadpool with no running loop, so the coroutine is submitted to the
    main loop captured at startup via run_coroutine_threadsafe. Previously
    these calls silently no-op'd on RuntimeError.
    """
    try:
        asyncio.get_running_loop().create_task(coro)
        return
    except RuntimeError:
        pass
    if _main_loop is not None and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _main_loop)
    else:
        coro.close()
        logger.warning("Broadcast dropped: no running event loop available")


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    """Main WebSocket endpoint for real-time updates.

    Validates JWT token via query parameter for authentication.
    In development without AUTH_PASSWORD, auth is bypassed.
    """
    # Authenticate: verify token if auth is configured
    if _effective_auth_password():
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return
        payload = verify_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid authentication token")
            return
    elif settings.app_env == "production":
        await websocket.close(code=4001, reason="Authentication not configured")
        return

    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle ping/pong or other client messages
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def notify_note_created(note_id: int, title: str):
    """Broadcast note creation to all clients."""
    await manager.broadcast(
        {
            "type": "note_created",
            "note_id": note_id,
            "title": title,
        }
    )


async def notify_note_updated(note_id: int, title: str):
    """Broadcast note update to all clients."""
    await manager.broadcast(
        {
            "type": "note_updated",
            "note_id": note_id,
            "title": title,
        }
    )


async def notify_xp_gained(xp: int, total_xp: int):
    """Broadcast XP gain to all clients."""
    await manager.broadcast(
        {
            "type": "xp_gained",
            "xp": xp,
            "total_xp": total_xp,
        }
    )


async def notify_streak_updated(streak: int):
    """Broadcast streak update to all clients."""
    await manager.broadcast(
        {
            "type": "streak_updated",
            "streak": streak,
        }
    )


async def notify_vault_synced(note_id: int, title: str, source_path: str | None = None):
    """Broadcast a vault-synced note to all clients (#73).

    Sent when a note is created or updated from the Obsidian vault so the
    frontend can distinguish vault syncs from manual edits.
    """
    await manager.broadcast(
        {
            "type": "vault_synced",
            "note_id": note_id,
            "title": title,
            "source_path": source_path,
        }
    )


async def notify_vault_sync_started():
    """Broadcast that a vault sync cycle has started (#73)."""
    await manager.broadcast({"type": "vault_sync_started"})


async def notify_vault_sync_complete(total_synced: int = 0):
    """Broadcast that a vault sync cycle has completed (#73)."""
    await manager.broadcast(
        {
            "type": "vault_sync_complete",
            "total_synced": total_synced,
        }
    )


def broadcast_note_created(note_id: int, title: str):
    """Synchronous trigger to broadcast note creation."""
    _schedule_broadcast(notify_note_created(note_id, title))


def broadcast_note_updated(note_id: int, title: str):
    """Synchronous trigger to broadcast note update."""
    _schedule_broadcast(notify_note_updated(note_id, title))


def broadcast_xp_gained(xp: int, total_xp: int):
    """Synchronous trigger to broadcast XP gain."""
    _schedule_broadcast(notify_xp_gained(xp, total_xp))


def broadcast_streak_updated(streak: int):
    """Synchronous trigger to broadcast streak update."""
    _schedule_broadcast(notify_streak_updated(streak))


def broadcast_vault_synced(note_id: int, title: str, source_path: str | None = None):
    """Synchronous trigger to broadcast a vault-synced note (#73)."""
    _schedule_broadcast(notify_vault_synced(note_id, title, source_path))


def broadcast_vault_sync_started():
    """Synchronous trigger to broadcast vault sync start (#73)."""
    _schedule_broadcast(notify_vault_sync_started())


def broadcast_vault_sync_complete(total_synced: int = 0):
    """Synchronous trigger to broadcast vault sync completion (#73)."""
    _schedule_broadcast(notify_vault_sync_complete(total_synced))
