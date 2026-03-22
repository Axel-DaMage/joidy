"""
Writes _joidy/ files into the Obsidian vault daily.
Runs once at startup, then every day at midnight.
"""

import asyncio
from datetime import date, datetime, timedelta

import httpx

from config import settings


async def write_joidy_files():
    """Call the API to trigger writing of all _joidy/ files."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.post(f"{settings.api_url}/vault/write-daily")
            await client.post(f"{settings.api_url}/vault/write-objectives")
            await client.post(f"{settings.api_url}/vault/write-skills")
            print(f"[writer] _joidy/ files updated at {datetime.now().isoformat()}")
        except Exception as e:
            print(f"[writer] Failed to write _joidy/ files: {e}")


async def schedule_daily_writes():
    """Run write_joidy_files at startup and then every day at midnight."""
    # Run immediately on startup
    await write_joidy_files()

    while True:
        now = datetime.now()
        tomorrow_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = (tomorrow_midnight - now).total_seconds()
        print(f"[writer] Next _joidy/ update in {seconds_until_midnight:.0f}s")
        await asyncio.sleep(seconds_until_midnight)
        await write_joidy_files()
