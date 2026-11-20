"""Shared worker → API credential with single-flight refresh (#1302).

Every worker task (vault watcher, _joidy/ daily writer, calendar sync)
authenticates to the API with the INTERNAL_API_TOKEN service credential
(#1275). Concurrent 401-retry paths used to race on an unguarded module
global, so a burst of 401s triggered a token-refresh stampede. All fetches
now funnel through one ``asyncio.Lock`` and waiters reuse the result of the
in-flight refresh, so N concurrent 401s perform exactly one fetch.
"""

import asyncio
import logging

import httpx
from config import settings

logger = logging.getLogger(__name__)

_auth_lock = asyncio.Lock()
_token_cache: str | None = None
# Bumped once per completed fetch; lets a force=True caller detect that
# another task already refreshed while it waited on the lock.
_refresh_generation = 0


async def _fetch_token(client: httpx.AsyncClient) -> str:
    """Perform the actual credential fetch.

    Isolated behind the lock so tests can count real fetches. The credential
    is currently the static INTERNAL_API_TOKEN; if it ever becomes a
    negotiated token, the fetch/refresh logic lives here — already
    single-flight.
    """
    return settings.internal_api_token or ""


async def get_auth_token(client: httpx.AsyncClient, *, force: bool = False) -> str:
    """Return the worker → API service token.

    ``force=True`` is used by 401 retry paths. A forcing caller records the
    refresh generation before taking the lock: if another task already
    refreshed while it waited, it reuses that result instead of fetching
    again — one refresh per wave of concurrent 401s, never a stampede.
    ``client`` is kept for signature parity with the per-task wrappers and
    for a future negotiated-token fetch.
    """
    global _token_cache, _refresh_generation
    seen = _refresh_generation
    async with _auth_lock:
        if _token_cache is None or (force and _refresh_generation == seen):
            _token_cache = await _fetch_token(client)
            _refresh_generation += 1
        return _token_cache
