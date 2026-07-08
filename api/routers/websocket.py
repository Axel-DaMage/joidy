"""
WebSocket endpoints for real-time updates.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


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
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates."""
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
    await manager.broadcast({
        "type": "note_created",
        "note_id": note_id,
        "title": title,
    })


async def notify_note_updated(note_id: int, title: str):
    """Broadcast note update to all clients."""
    await manager.broadcast({
        "type": "note_updated",
        "note_id": note_id,
        "title": title,
    })


async def notify_xp_gained(xp: int, total_xp: int):
    """Broadcast XP gain to all clients."""
    await manager.broadcast({
        "type": "xp_gained",
        "xp": xp,
        "total_xp": total_xp,
    })


async def notify_streak_updated(streak: int):
    """Broadcast streak update to all clients."""
    await manager.broadcast({
        "type": "streak_updated",
        "streak": streak,
    })


def broadcast_note_created(note_id: int, title: str):
    """Synchronous trigger to broadcast note creation."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(notify_note_created(note_id, title))
    except RuntimeError:
        pass


def broadcast_note_updated(note_id: int, title: str):
    """Synchronous trigger to broadcast note update."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(notify_note_updated(note_id, title))
    except RuntimeError:
        pass


def broadcast_xp_gained(xp: int, total_xp: int):
    """Synchronous trigger to broadcast XP gain."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(notify_xp_gained(xp, total_xp))
    except RuntimeError:
        pass


def broadcast_streak_updated(streak: int):
    """Synchronous trigger to broadcast streak update."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(notify_streak_updated(streak))
    except RuntimeError:
        pass
