"""Shared task-liveness registry for the worker background tasks (#644).

The worker runs two long-lived asyncio tasks (vault watcher + daily writer).
Previously ``asyncio.gather(..., return_exceptions=True)`` silently swallowed
crashes, so a dead task went unnoticed. This registry is updated by the task
supervisor in ``main.py`` and read by the ``/health`` endpoint in
``metrics_server.py`` (which runs in a separate thread), so it is guarded by a
lock to stay thread-safe across the asyncio loop and the HTTP server thread.
"""

import threading
import time

_lock = threading.Lock()
_tasks: dict[str, dict] = {}


def _entry(state: str, error: str | None = None) -> dict:
    return {"state": state, "last_activity": time.time(), "error": error}


def record_start(name: str) -> None:
    """Register a task as running (called when the task is about to start)."""
    with _lock:
        _tasks[name] = _entry("running")


def record_activity(name: str) -> None:
    """Refresh the last-seen-alive timestamp for a running task (heartbeat)."""
    with _lock:
        entry = _tasks.setdefault(name, _entry("running"))
        entry["state"] = "running"
        entry["last_activity"] = time.time()


def mark_crashed(name: str, exc: BaseException) -> None:
    """Record that a task crashed with ``exc`` (surfaced via /health)."""
    with _lock:
        entry = _tasks.setdefault(name, _entry("crashed"))
        entry["state"] = "crashed"
        entry["last_activity"] = time.time()
        entry["error"] = repr(exc)


def mark_stopped(name: str) -> None:
    """Record that a task stopped cleanly (e.g. during graceful shutdown)."""
    with _lock:
        entry = _tasks.setdefault(name, _entry("stopped"))
        entry["state"] = "stopped"
        entry["last_activity"] = time.time()


def snapshot() -> dict[str, dict]:
    """Return a point-in-time copy of every task's liveness state."""
    with _lock:
        return {name: dict(entry) for name, entry in _tasks.items()}


def overall_status() -> str:
    """``"ok"`` when every known task is running, ``"degraded"`` otherwise."""
    with _lock:
        if not _tasks:
            return "ok"
        return "degraded" if any(e["state"] == "crashed" for e in _tasks.values()) else "ok"
