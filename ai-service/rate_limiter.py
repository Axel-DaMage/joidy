"""
Shared pacing rate limiter for provider API calls.

Every provider-bound endpoint draws from a single schedule, so the aggregate
request rate stays within the configured budget (free tier: 15 RPM) — not
per endpoint (#1539).
"""

import asyncio
import time


class RateLimiter:
    """Paces requests by ``interval = 60 / max_per_minute`` seconds.

    ``acquire()`` reserves the next free slot under the lock — O(1)
    bookkeeping — then waits *outside* the lock, so queued callers sleep in
    parallel and the lock is never held across a sleep (#1539). A caller
    cancelled mid-wait keeps its reservation (conservative: the slot is
    still counted against the budget).
    """

    def __init__(self, max_per_minute: int = 12):
        self._next_slot = 0.0
        self._lock = asyncio.Lock()
        self.set_rate(max_per_minute)

    def set_rate(self, max_per_minute: int) -> None:
        """Update the pacing rate (clamped to >= 1 RPM to avoid div-by-zero)."""
        self.max_per_minute = max(1, max_per_minute)
        self.interval = 60.0 / self.max_per_minute

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + self.interval
            wait = start - now
        if wait > 0:
            await asyncio.sleep(wait)


_limiters: dict[str, RateLimiter] = {}


def get_limiter(max_per_minute: int = 12, name: str = "default") -> RateLimiter:
    """Return the shared provider rate limiter.

    All names resolve to the same pacing schedule so the aggregate request
    rate across endpoints (embed, classify, rag, cluster, chat, ...) cannot
    exceed the configured provider budget (#1539). Per-endpoint buckets let
    ~6 endpoints each spend ``max_requests_per_minute`` independently, so
    ``name`` is kept only for call-site readability and possible future
    per-endpoint weighting.

    Calling again with a different ``max_per_minute`` reconfigures the
    shared limiter — the argument is always honored (previously it was
    silently ignored after the first call).
    """
    target = max(1, max_per_minute)
    limiter = next(iter(_limiters.values()), None)
    if limiter is None:
        limiter = RateLimiter(target)
    elif limiter.max_per_minute != target:
        limiter.set_rate(target)
    _limiters[name] = limiter
    return limiter
