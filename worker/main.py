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

# Restart policy for crashed background tasks (#815). A cold-start race
# (e.g. the API still running migrations) used to crash vault_watcher once
# and leave it dead forever — the worker stayed unhealthy until a manual
# `docker compose restart worker`. The supervisor now restarts the task
# with exponential backoff up to MAX_RESTARTS times; only after that many
# consecutive crashes does it surface as unhealthy (current behavior), so
# a permanently broken task is still visible instead of looping silently.
MAX_RESTARTS = 5
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 60.0


async def _heartbeat(name: str) -> None:
    """Refresh the last-seen-alive timestamp for ``name`` while it runs."""
    while True:
        record_activity(name)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def _supervise(name: str, coro_factory) -> None:
    """Run a background task with restart-on-crash semantics.

    Replaces the old ``asyncio.gather(..., return_exceptions=True)`` pattern
    (#644): exceptions are logged at ERROR level and recorded in the shared
    task-status registry so ``/health`` reports ``degraded``.

    ``coro_factory`` is a zero-arg callable returning a fresh coroutine each
    call — a coroutine cannot be awaited twice, so a factory is required to
    support restarts. On crash, the task is restarted with exponential
    backoff (1s, 2s, 4s, ... capped at 60s) up to ``MAX_RESTARTS`` times
    (#815). A task that crashes that many times in a row is marked crashed
    (surfaced via /health) instead of looping forever. Clean completion
    exits immediately; ``CancelledError`` (graceful shutdown) propagates.
    """
    record_start(name)
    heartbeat = asyncio.create_task(_heartbeat(name), name=f"{name}_heartbeat")
    restarts = 0
    backoff = INITIAL_BACKOFF
    try:
        while True:
            try:
                await coro_factory()
                # Clean exit — task finished on its own. No restart.
                return
            except asyncio.CancelledError:
                mark_stopped(name)
                raise
            except Exception as exc:
                if restarts >= MAX_RESTARTS:
                    logger.exception(
                        "[worker] Task %s crashed %d times in a row; giving up",
                        name,
                        restarts + 1,
                    )
                    mark_crashed(name, exc)
                    return
                restarts += 1
                logger.warning(
                    "[worker] Task %s crashed (%d/%d): %s — restarting in %.1fs",
                    name,
                    restarts,
                    MAX_RESTARTS,
                    exc,
                    backoff,
                    exc_info=True,
                )
                # Do NOT mark crashed during retry — only mark it after
                # MAX_RESTARTS consecutive failures (above). Marking crashed
                # here would make /health oscillate between 200/503 during
                # the backoff window, and the Docker healthcheck (10s
                # interval, 5 retries) could catch a 503 snapshot and mark
                # the container unhealthy while it is actively recovering
                # — defeating the purpose of the retry (#815).
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    mark_stopped(name)
                    raise
                backoff = min(backoff * 2, MAX_BACKOFF)
                record_start(name)
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
        asyncio.create_task(_supervise("vault_watcher", watch_vault), name="vault_watcher"),
        asyncio.create_task(_supervise("daily_writer", schedule_daily_writes), name="daily_writer"),
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
