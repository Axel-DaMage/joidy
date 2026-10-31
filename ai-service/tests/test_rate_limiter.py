"""Unit tests for rate_limiter.RateLimiter (token-bucket pacing)."""

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
        # 6000 rpm -> 10 ms interval: fast but still exercises the sleep path.
        limiter = RateLimiter(max_per_minute=6000)
        await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, limiter.interval * 0.8)

    async def test_interval_computed_from_max_per_minute(self):
        limiter = RateLimiter(max_per_minute=30)
        self.assertAlmostEqual(limiter.interval, 2.0)

    async def test_interval_remaining_zero_after_long_pause(self):
        limiter = RateLimiter(max_per_minute=60)
        limiter._last_call = time.monotonic() - 120.0
        self.assertEqual(limiter._interval_remaining(time.monotonic()), 0.0)


class TestGetLimiter(unittest.TestCase):
    def setUp(self):
        rate_limiter._limiter = None

    def tearDown(self):
        rate_limiter._limiter = None

    def test_get_limiter_returns_singleton(self):
        first = get_limiter()
        second = get_limiter()
        self.assertIs(first, second)

    def test_get_limiter_respects_max_per_minute(self):
        limiter = get_limiter(max_per_minute=15)
        self.assertEqual(limiter.max_per_minute, 15)


if __name__ == "__main__":
    unittest.main()
