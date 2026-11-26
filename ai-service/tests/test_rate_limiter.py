"""Unit tests for rate_limiter.RateLimiter (shared provider budget, #1539)."""

import asyncio
import time
import unittest

import rate_limiter
from rate_limiter import RateLimiter, get_limiter


class TestRateLimiter(unittest.IsolatedAsyncioTestCase):
    async def test_first_acquire_is_immediate(self):
        limiter = RateLimiter(max_per_minute=60)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)

    async def test_acquire_spaces_calls_by_interval(self):
        # 6000 rpm -> 10 ms interval: fast but still exercises the wait path.
        limiter = RateLimiter(max_per_minute=6000)
        await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, limiter.interval * 0.8)

    async def test_concurrent_acquires_get_distinct_slots(self):
        # Reservations are stamped under the lock: N concurrent callers are
        # assigned consecutive slots ~interval apart, so the burst drains at
        # the configured rate instead of firing all at once — and no caller
        # waits longer than its own slot requires.
        limiter = RateLimiter(max_per_minute=6000)  # 10 ms slots
        start = time.monotonic()
        await asyncio.gather(*(limiter.acquire() for _ in range(4)))
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, limiter.interval * 3 * 0.8)
        self.assertLess(elapsed, limiter.interval * 3 + 0.5)

    async def test_lock_is_not_held_while_waiting(self):
        # Regression for #1539: the wait must happen outside the critical
        # section so a queued request cannot serialize callers behind its
        # sleep.
        limiter = RateLimiter(max_per_minute=60)  # 1 s interval
        await limiter.acquire()  # consume the immediate slot
        task = asyncio.create_task(limiter.acquire())
        await asyncio.sleep(0.05)  # let it reserve its slot and start waiting
        self.assertFalse(limiter._lock.locked())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_interval_computed_from_max_per_minute(self):
        limiter = RateLimiter(max_per_minute=30)
        self.assertAlmostEqual(limiter.interval, 2.0)

    async def test_idle_period_resets_schedule(self):
        # After a long pause the next acquire is immediate — no accumulated
        # debt from the schedule.
        limiter = RateLimiter(max_per_minute=60)
        limiter._next_slot = time.monotonic() - 120.0
        start = time.monotonic()
        await limiter.acquire()
        self.assertLess(time.monotonic() - start, 0.05)


class TestGetLimiter(unittest.TestCase):
    def setUp(self):
        rate_limiter._limiters.clear()

    def tearDown(self):
        rate_limiter._limiters.clear()

    def test_get_limiter_returns_singleton(self):
        first = get_limiter()
        second = get_limiter()
        self.assertIs(first, second)

    def test_get_limiter_respects_max_per_minute(self):
        limiter = get_limiter(max_per_minute=15)
        self.assertEqual(limiter.max_per_minute, 15)

    def test_all_names_share_one_budget(self):
        # #1539: distinct names must NOT get independent buckets — per-
        # endpoint buckets let the aggregate exceed the provider budget by
        # ~6x (6 names x max_requests_per_minute).
        embed = get_limiter(12, name="embed")
        chat = get_limiter(12, name="chat")
        rag = get_limiter(12, name="rag")
        self.assertIs(embed, chat)
        self.assertIs(chat, rag)

    def test_same_name_reuses_and_honors_new_rpm(self):
        first = get_limiter(12, name="rag")
        again = get_limiter(60, name="rag")
        self.assertIs(first, again)
        self.assertEqual(again.max_per_minute, 60)
        self.assertAlmostEqual(again.interval, 1.0)

    def test_new_rpm_reconfigures_shared_limiter(self):
        get_limiter(12, name="embed")
        shared = get_limiter(60, name="chat")
        self.assertEqual(shared.max_per_minute, 60)

    def test_rpm_clamped_to_minimum_one(self):
        self.assertEqual(get_limiter(0).max_per_minute, 1)


class TestSharedBudgetEnforcement(unittest.IsolatedAsyncioTestCase):
    """Aggregate RPM across endpoints cannot exceed the configured budget."""

    def setUp(self):
        rate_limiter._limiters.clear()

    def tearDown(self):
        rate_limiter._limiters.clear()

    async def test_aggregate_rate_across_endpoints(self):
        # 600 rpm -> 100 ms interval. One burst from every named "endpoint"
        # must drain through a single schedule: ~5 intervals wall time.
        # With per-endpoint buckets this finished in under one interval.
        names = ("embed", "classify", "rag", "cluster", "chat", "default")
        limiters = [get_limiter(600, name=n) for n in names]
        start = time.monotonic()
        await asyncio.gather(*(lim.acquire() for lim in limiters))
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.1 * (len(names) - 1) * 0.8)
        self.assertLess(elapsed, 0.1 * (len(names) - 1) + 0.5)

    async def test_interleaved_endpoints_share_schedule(self):
        # Alternating acquires from two names are still spaced one interval
        # apart — the budget is enforced across, not within, endpoints.
        embed = get_limiter(600, name="embed")  # 100 ms interval
        chat = get_limiter(600, name="chat")
        await embed.acquire()
        start = time.monotonic()
        await chat.acquire()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, embed.interval * 0.8)


if __name__ == "__main__":
    unittest.main()
