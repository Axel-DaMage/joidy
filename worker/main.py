"""
Joidy Worker — runs background tasks concurrently:
1. Obsidian vault watcher (file sync)
2. Daily _joidy/ writer
"""

import asyncio
import contextlib
import logging
import signal

from logging_config import setup_logging
from metrics_server import start_metrics_server
from tasks.joidy_daily_writer import schedule_daily_writes
from task_status import mark_crashed, mark_stopped, record_activity, record_start
from watchers.vault_watcher import shutdown_event, watch_vault

logger = logging.getLogger(__name__)

SHUTDOWN_TIMEOUT = 15.0
HEARTBEAT_INTERVAL = 30.0


async def _heartbeat(name: str) -> None:
    """Refresh the last-seen-alive timestamp for ``name`` while it runs."""
    while True:
        record_activity(name)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def _supervise(name: str, coro) -> None:
    """Run a background task, surfacing crashes instead of swallowing them.

    Replaces the old ``asyncio.gather(..., return_exceptions=True)`` pattern
    (#644): exceptions are logged at ERROR level and recorded in the shared
    task-status registry so ``/health`` reports ``degraded``. The exception is
    not re-raised so a single crashed task does not take down its sibling —
    the crash is surfaced via the health endpoint and the ERROR log instead.
    """
    record_start(name)
    heartbeat = asyncio.create_task(_heartbeat(name), name=f"{name}_heartbeat")
    try:
        await coro
    except asyncio.CancelledError:
        mark_stopped(name)
        raise
    except Exception as exc:
        logger.error("[worker] Task %s crashed: %s", name, exc, exc_info=True)
        mark_crashed(name, exc)
        return
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat


async def main():
    setup_logging()
    logger.info("[worker] Joidy Worker starting...")

    # Start the Prometheus metrics server so the worker is scrapable (#406).
    # It also serves /health, which reflects task liveness from task_status.
    start_metrics_server()

    tasks = [
        asyncio.create_task(_supervise("vault_watcher", watch_vault()), name="vault_watcher"),
        asyncio.create_task(_supervise("daily_writer", schedule_daily_writes()), name="daily_writer"),
    ]

    def shutdown(sig):
        # Two-phase graceful shutdown (#371):
        # Phase 1: signal the watcher to stop accepting new filesystem events
        # (shutdown_event) so it can drain its in-memory queue. We do NOT
        # cancel tasks immediately — that would interrupt mid-flight writes.
        logger.info("[worker] Signal %s received, beginning graceful shutdown...", sig.name)
        shutdown_event.set()
        # The daily writer has no event loop to poll, so cancel it directly.
        for task in tasks:
            if task.get_name() != "vault_watcher":
                task.cancel()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: shutdown(s))

    try:
        # No return_exceptions=True: _supervise catches and records crashes so
        # they surface via /health (degraded) and ERROR logs instead of being
        # silently swallowed.
        await asyncio.gather(*tasks)
    finally:
        remaining = [t for t in tasks if not t.done()]
        if remaining:
            _, pending = await asyncio.wait(remaining, timeout=SHUTDOWN_TIMEOUT)
            for t in pending:
                t.cancel()
                logger.warning("[worker] Task %s forcefully cancelled after timeout", t.get_name())
        logger.info("[worker] Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
