"""
Token-bucket rate limiter for provider API calls.
Stays within free tier (15 RPM) by default.
"""

import asyncio
import time


class RateLimiter:
    def __init__(self, max_per_minute: int = 12):
        self._last_call = 0.0
        self._lock = asyncio.Lock()
        self.set_rate(max_per_minute)

    def set_rate(self, max_per_minute: int) -> None:
        """Update the pacing rate (clamped to >= 1 RPM to avoid div-by-zero)."""
        self.max_per_minute = max(1, max_per_minute)
        self.interval = 60.0 / self.max_per_minute

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._interval_remaining(now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    def _interval_remaining(self, now: float) -> float:
        elapsed = now - self._last_call
        return max(0.0, self.interval - elapsed)


_limiters: dict[str, RateLimiter] = {}


def get_limiter(max_per_minute: int = 12, name: str = "default") -> RateLimiter:
    """Return the shared rate limiter for ``name``.

    Each distinct name gets its own limiter so different endpoints are not
    serialized on a single global lock during bursts (#1330). Calling again
    for the same name with a different ``max_per_minute`` reconfigures the
    limiter — the argument is always honored (previously it was silently
    ignored after the first call).
    """
    target = max(1, max_per_minute)
    limiter = _limiters.get(name)
    if limiter is None:
        limiter = RateLimiter(target)
        _limiters[name] = limiter
    elif limiter.max_per_minute != target:
        limiter.set_rate(target)
    return limiter
