"""
Joidy Worker — runs background tasks concurrently:
1. Obsidian vault watcher (file sync)
2. Daily _joidy/ writer
"""

import asyncio
import logging
import signal

from logging_config import setup_logging
from metrics_server import start_metrics_server
from tasks.joidy_daily_writer import schedule_daily_writes
from watchers.vault_watcher import shutdown_event, watch_vault

logger = logging.getLogger(__name__)

SHUTDOWN_TIMEOUT = 15.0


async def main():
    setup_logging()
    logger.info("[worker] Joidy Worker starting...")

    # Start the Prometheus metrics server so the worker is scrapable (#406).
    start_metrics_server()

    tasks = [
        asyncio.create_task(watch_vault(), name="vault_watcher"),
        asyncio.create_task(schedule_daily_writes(), name="daily_writer"),
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
        await asyncio.gather(*tasks, return_exceptions=True)
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
