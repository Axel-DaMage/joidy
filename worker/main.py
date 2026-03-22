"""
Joidy Worker — runs background tasks concurrently:
1. Obsidian vault watcher (file sync)
2. Daily _joidy/ writer
"""

import asyncio
import signal
import sys

from watchers.vault_watcher import watch_vault
from tasks.joidy_daily_writer import schedule_daily_writes


async def main():
    print("[worker] Joidy Worker starting...")

    tasks = [
        asyncio.create_task(watch_vault(), name="vault_watcher"),
        asyncio.create_task(schedule_daily_writes(), name="daily_writer"),
    ]

    def shutdown(sig):
        print(f"\n[worker] Signal {sig.name} received, shutting down...")
        for task in tasks:
            task.cancel()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: shutdown(s))

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        print("[worker] Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
