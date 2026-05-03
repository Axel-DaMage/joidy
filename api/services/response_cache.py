from __future__ import annotations

from functools import wraps
from inspect import signature
from threading import RLock
from time import monotonic
from typing import Any, Callable, TypeVar


F = TypeVar("F", bound=Callable[..., Any])


class _TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds

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
                        return hit[1]
                value = func(*args, **kwargs)
                with lock:
                    values[key] = (now, value)
                return value

            def cache_clear() -> None:
                with lock:
                    values.clear()

            cached.cache_clear = cache_clear  # type: ignore[attr-defined]
            return cached  # type: ignore[return-value]

        return wrap


_cache = _TTLCache(ttl_seconds=5.0)


def ttl_cache(*, ignore_params: set[str] | None = None):
    return _cache.decorator(ignore_params=ignore_params)


def clear_api_caches() -> None:
    for func in _REGISTERED_CLEARERS:
        func()


_REGISTERED_CLEARERS: list[Callable[[], None]] = []


def register_cache_clearer(clearer: Callable[[], None]) -> None:
    _REGISTERED_CLEARERS.append(clearer)