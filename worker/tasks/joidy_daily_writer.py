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
from logging_config import get_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)

# Cached auth token — refreshed when it expires
_auth_token: str | None = None


async def _get_auth_token(client: httpx.AsyncClient) -> str | None:
    """Login to the API and return a bearer token (#266)."""
    global _auth_token
    if _auth_token:
        return _auth_token
    if not settings.auth_password:
        logger.warning("[writer] No AUTH_PASSWORD configured — vault writes will fail")
        return None
    try:
        resp = await client.post(
            f"{settings.api_url}/auth/login",
            json={"password": settings.auth_password},
        )
        resp.raise_for_status()
        _auth_token = resp.json().get("access_token")
        return _auth_token
    except Exception as e:
        logger.error("[writer] Failed to authenticate with API: %s", e)
        return None


async def write_joidy_files():
    """Call the API to trigger writing of all _joidy/ files."""
    global _auth_token
    cid = set_correlation_id(f"writer-{uuid.uuid4().hex[:12]}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            token = await _get_auth_token(client)
            headers = {"X-Request-ID": cid}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            responses = await asyncio.gather(
                client.post(f"{settings.api_url}/vault/write-daily", headers=headers),
                client.post(f"{settings.api_url}/vault/write-objectives", headers=headers),
                client.post(f"{settings.api_url}/vault/write-skills", headers=headers),
                return_exceptions=True,
            )

            # If any response is 401, refresh token and retry once
            need_retry = any(
                isinstance(r, httpx.Response) and r.status_code == 401 for r in responses
            )
            if need_retry:
                logger.warning("[writer] Auth token expired, refreshing...")
                _auth_token = None
                token = await _get_auth_token(client)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    await asyncio.gather(
                        client.post(f"{settings.api_url}/vault/write-daily", headers=headers),
                        client.post(f"{settings.api_url}/vault/write-objectives", headers=headers),
                        client.post(f"{settings.api_url}/vault/write-skills", headers=headers),
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
