"""
Periodic Google Calendar sync (#1134).

Triggers the API's POST /integrations/google/calendar/sync every
CALENDAR_SYNC_INTERVAL seconds so the local event cache stays fresh even
when the frontend is closed. The actual Google API calls (tokens, sync
tokens, upserts) live in the API — the worker only pulls the trigger.
"""

import asyncio
import logging
import uuid

import httpx
from config import settings
from logging_config import set_correlation_id
from tasks import joidy_daily_writer

logger = logging.getLogger(__name__)


async def trigger_calendar_sync() -> bool:
    """Ask the API to sync Google Calendars once. Returns True on success."""
    cid = set_correlation_id(f"cal-sync-{uuid.uuid4().hex[:12]}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        token = await joidy_daily_writer._get_auth_token(client)
        headers = {"X-Request-ID": cid}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = await client.post(f"{settings.api_url}/integrations/google/calendar/sync", headers=headers)

        if resp.status_code == 401:
            # Cached API token expired — re-authenticate and retry once.
            logger.warning("[calendar] Auth token expired, refreshing...")
            joidy_daily_writer._auth_token = None
            token = await joidy_daily_writer._get_auth_token(client)
            if token:
                headers["Authorization"] = f"Bearer {token}"
                resp = await client.post(f"{settings.api_url}/integrations/google/calendar/sync", headers=headers)

        if resp.status_code == 401:
            logger.info("[calendar] Google no está conectado — sync omitido")
            return False
        resp.raise_for_status()

        data = resp.json()
        calendars = data.get("calendars", [])
        synced = sum(1 for c in calendars if "error" not in c)
        logger.info("[calendar] Sync OK: %d/%d calendars", synced, len(calendars))
        return True


async def calendar_sync_loop():
    """Trigger a Google Calendar sync periodically (first run after one interval)."""
    while True:
        await asyncio.sleep(settings.calendar_sync_interval)
        try:
            await trigger_calendar_sync()
        except Exception as e:
            logger.error("[calendar] Sync failed: %s", e)
