from __future__ import annotations

import logging
from functools import wraps
from inspect import signature
from threading import RLock
from time import monotonic
from typing import Any, Callable, TypeVar


logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


class _CacheStats:
    """Thread-safe cache hit/miss counters."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def record_hit(self) -> None:
        with self._lock:
            self.hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self.misses += 1

    def record_eviction(self) -> None:
        with self._lock:
            self.evictions += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "total": total,
                "hit_rate_pct": int(self.hits / total * 100) if total > 0 else 0,
            }


class _TTLCache:
    def __init__(self, ttl_seconds: float, max_entries: int = 256):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.stats = _CacheStats()

    def decorator(self, ignore_params: set[str] | None = None) -> Callable[[F], F]:
        ignore_params = ignore_params or set()

        def wrap(func: F) -> F:
            values: dict[tuple[Any, ...], tuple[float, Any]] = {}
            lock = RLock()
            param_names = tuple(signature(func).parameters)

            @wraps(func)
            def cached(*args: Any, **kwargs: Any):
                bound = signature(func).bind_partial(*args, **kwargs)
                key = tuple(
                    (name, bound.arguments.get(name))
                    for name in param_names
                    if name not in ignore_params and name in bound.arguments
                )
                now = monotonic()
                with lock:
                    hit = values.get(key)
                    if hit and now - hit[0] < self.ttl_seconds:
                        self.stats.record_hit()
                        return hit[1]

                self.stats.record_miss()
                value = func(*args, **kwargs)
                with lock:
                    # Evict stale entries if at capacity
                    if len(values) >= self.max_entries:
                        stale_keys = [
                            k for k, (ts, _) in values.items()
                            if now - ts >= self.ttl_seconds
                        ]
                        for k in stale_keys:
                            del values[k]
                            self.stats.record_eviction()
                        # If still at capacity, remove oldest entry
                        if len(values) >= self.max_entries:
                            oldest_key = min(values, key=lambda k: values[k][0])
                            del values[oldest_key]
                            self.stats.record_eviction()

                    values[key] = (now, value)
                return value

            def cache_clear() -> None:
                with lock:
                    evicted = len(values)
                    values.clear()
                    for _ in range(evicted):
                        self.stats.record_eviction()

            cached.cache_clear = cache_clear  # type: ignore[attr-defined]
            return cached  # type: ignore[return-value]

        return wrap


_cache = _TTLCache(ttl_seconds=5.0, max_entries=256)


def ttl_cache(*, ignore_params: set[str] | None = None):
    return _cache.decorator(ignore_params=ignore_params)


def clear_api_caches() -> None:
    for func in _REGISTERED_CLEARERS:
        func()


_REGISTERED_CLEARERS: list[Callable[[], None]] = []


def register_cache_clearer(clearer: Callable[[], None]) -> None:
    _REGISTERED_CLEARERS.append(clearer)


def get_cache_stats() -> dict[str, Any]:
    """Return cache performance statistics."""
    return {
        "initialized": True,
        "ttl_seconds": _cache.ttl_seconds,
        "max_entries": _cache.max_entries,
        "registered_clearers": len(_REGISTERED_CLEARERS),
        **_cache.stats.snapshot(),
    }