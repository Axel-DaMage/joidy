"""
Token-bucket rate limiter for Gemini API.
Stays within free tier (15 RPM) by default.
"""

import asyncio
import time


class RateLimiter:
    def __init__(self, max_per_minute: int = 12):
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute
        self._last_call = 0.0
        self._lock = asyncio.Lock()

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


_limiter: RateLimiter | None = None


def get_limiter(max_per_minute: int = 12) -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(max_per_minute)
    return _limiter
