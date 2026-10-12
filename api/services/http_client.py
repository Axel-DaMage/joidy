"""Shared httpx.AsyncClient pool — one client per timeout profile (#998).

Creating a fresh AsyncClient per request pays a new TCP+TLS handshake and
skips connection reuse/keep-alive on hot paths (embeddings, AI calls,
integrations). This module hands out pooled clients keyed by timeout so
call sites keep their `async with` shape without closing shared state.

Usage:
    async with http_client(timeout=30.0) as client:
        resp = await client.get(...)

Register `aclose_http_clients` on app shutdown (main.py lifespan).
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

_clients: dict[float, httpx.AsyncClient] = {}


@asynccontextmanager
async def http_client(timeout: float = 30.0) -> AsyncIterator[httpx.AsyncClient]:
    client = _clients.get(timeout)
    if client is None or client.is_closed:
        client = _clients[timeout] = httpx.AsyncClient(timeout=timeout)
    yield client


async def aclose_http_clients() -> None:
    for client in _clients.values():
        if not client.is_closed:
            await client.aclose()
    _clients.clear()
