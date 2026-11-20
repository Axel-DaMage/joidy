"""
Writes _joidy/ files into the Obsidian vault daily.
Runs once at startup, then every day at midnight.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from config import settings
from logging_config import set_correlation_id

logger = logging.getLogger(__name__)


async def _get_auth_token(client: httpx.AsyncClient) -> str | None:
    """Return the INTERNAL_API_TOKEN service credential (#1275).

    The worker authenticates to the API with a dedicated service token
    instead of logging in with AUTH_PASSWORD. Kept async with the ``client``
    parameter so callers are unchanged.
    """
    if not settings.internal_api_token:
        logger.warning("[writer] No INTERNAL_API_TOKEN configured — vault writes will fail")
        return None
    return settings.internal_api_token


async def write_joidy_files():
    """Call the API to trigger writing of all _joidy/ files."""
    cid = set_correlation_id(f"writer-{uuid.uuid4().hex[:12]}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            token = await _get_auth_token(client)
            headers = {"X-Request-ID": cid}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            await asyncio.gather(
                client.post(f"{settings.api_url}/vault/write-daily", headers=headers),
                client.post(f"{settings.api_url}/vault/write-objectives", headers=headers),
                client.post(f"{settings.api_url}/vault/write-skills", headers=headers),
                return_exceptions=True,
            )

            logger.info("[writer] _joidy/ files updated at %s", datetime.now(UTC).isoformat())
        except Exception as e:
            logger.exception("[writer] Failed to write _joidy/ files: %s", e)


async def schedule_daily_writes():
    """Run write_joidy_files at startup and then every day at midnight."""
    # Run immediately on startup
    await write_joidy_files()

    while True:
        now = datetime.now(UTC)
        tomorrow_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        seconds_until_midnight = (tomorrow_midnight - now).total_seconds()
        logger.info("[writer] Next _joidy/ update in %.0fs", seconds_until_midnight)
        await asyncio.sleep(seconds_until_midnight)
        await write_joidy_files()
