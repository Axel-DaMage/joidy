"""In-process TTL + size-bounded response cache for AI provider calls.

Avoids re-calling providers for identical inputs (same text + model). The
model is part of the cache key so changing the configured model invalidates
stale entries automatically.

This is a simple in-memory cache suitable for a single ai-service instance.
For multi-instance deployments a shared store (e.g. Redis) would be needed,
but that is out of scope here and the project does not currently run multiple
ai-service replicas.
"""

import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from config import settings


class TTLCache:
    def __init__(self, max_size: int, ttl_seconds: float):
        self._max_size = max(max_size, 1)
        self._ttl = max(0.0, ttl_seconds)
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = Lock()

    def _is_expired(self, ts: float) -> bool:
        return self._ttl <= 0 or (time.monotonic() - ts) >= self._ttl

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, value = entry
            if self._is_expired(ts):
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.monotonic(), value)
            self._data.move_to_end(key)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = TTLCache(max_size=settings.cache_max_size, ttl_seconds=settings.cache_ttl_seconds)


def cache_key(*parts: str) -> str:
    """Build a stable SHA-256 cache key from the given string parts."""
    raw = "\x1f".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cache() -> TTLCache:
    return _cache
