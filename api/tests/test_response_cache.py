"""Unit tests for response_cache — TTL cache hit/miss, clear, stats, and expiry.

The cache module is pure (no DB), so these tests exercise the _TTLCache and the
module-level helpers (clear_api_caches, get_cache_stats) directly.
"""

import sys
import types
import unittest

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

import services.response_cache as response_cache_module
from services.response_cache import (
    _TTLCache,
    clear_api_caches,
    get_cache_stats,
    register_cache_clearer,
    ttl_cache,
)


class TTLCacheHitMissTest(unittest.TestCase):
    def test_cache_hit_on_repeat_call(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x * 2

        self.assertEqual(func(5), 10)
        self.assertEqual(func(5), 10)  # cached
        self.assertEqual(len(calls), 1)  # not re-executed

    def test_cache_miss_on_different_args(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x * 2

        self.assertEqual(func(1), 2)
        self.assertEqual(func(2), 4)
        self.assertEqual(len(calls), 2)

    def test_cache_miss_on_different_kwargs(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(a, b=0):
            calls.append((a, b))
            return a + b

        self.assertEqual(func(1, b=2), 3)
        self.assertEqual(func(1, b=3), 4)  # different b → miss
        self.assertEqual(len(calls), 2)


class TTLCacheClearTest(unittest.TestCase):
    def test_cache_clear_resets_cache(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x

        func(1)
        func(1)  # hit
        self.assertEqual(len(calls), 1)

        func.cache_clear()
        func(1)  # miss after clear
        self.assertEqual(len(calls), 2)

    def test_clear_api_caches_invokes_registered_clearers(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x

        register_cache_clearer(func.cache_clear)
        func(1)
        func(1)
        self.assertEqual(len(calls), 1)

        clear_api_caches()
        func(1)
        self.assertEqual(len(calls), 2)


class TTLCacheStatsTest(unittest.TestCase):
    def setUp(self):
        # Swap the module-level _cache for a fresh instance so stats are
        # isolated per test and get_cache_stats() reflects only our calls.
        self._orig_cache = response_cache_module._cache
        self._orig_clearers = list(response_cache_module._REGISTERED_CLEARERS)
        response_cache_module._cache = _TTLCache(ttl_seconds=60.0)
        response_cache_module._REGISTERED_CLEARERS.clear()

    def tearDown(self):
        response_cache_module._cache = self._orig_cache
        response_cache_module._REGISTERED_CLEARERS.clear()
        response_cache_module._REGISTERED_CLEARERS.extend(self._orig_clearers)

    def test_get_cache_stats_returns_hits_misses(self):
        @ttl_cache()
        def func(x):
            return x

        func(1)  # miss
        func(1)  # hit
        func(2)  # miss

        stats = get_cache_stats()
        self.assertTrue(stats["initialized"])
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 2)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["hit_rate_pct"], 33)

    def test_get_cache_stats_includes_config(self):
        stats = get_cache_stats()
        self.assertEqual(stats["ttl_seconds"], 60.0)
        self.assertEqual(stats["max_entries"], 256)
        self.assertIn("registered_clearers", stats)


class TTLCacheExpiryTest(unittest.TestCase):
    def test_ttl_expiry_returns_stale_and_re_executes(self):
        cache = _TTLCache(ttl_seconds=0.05)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x

        func(1)
        self.assertEqual(len(calls), 1)
        # Wait for TTL to expire.
        import time

        time.sleep(0.1)
        func(1)  # expired → re-execute
        self.assertEqual(len(calls), 2)

    def test_ttl_not_expired_within_window(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x

        func(1)
        func(1)
        self.assertEqual(len(calls), 1)  # still cached


class TTLCacheIgnoreParamsTest(unittest.TestCase):
    def test_ignore_params_excludes_from_key(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator(ignore_params={"token"})
        def func(x, token=""):
            calls.append(x)
            return x

        self.assertEqual(func(1, token="a"), 1)
        self.assertEqual(func(1, token="b"), 1)  # token ignored → hit
        self.assertEqual(len(calls), 1)

    def test_db_param_always_ignored(self):
        cache = _TTLCache(ttl_seconds=60.0)
        calls = []

        @cache.decorator()
        def func(x, db=None):
            calls.append(x)
            return x

        self.assertEqual(func(1, db="session1"), 1)
        self.assertEqual(func(1, db="session2"), 1)  # db ignored → hit
        self.assertEqual(len(calls), 1)


class TTLCacheEvictionTest(unittest.TestCase):
    def test_max_entries_evicts_oldest(self):
        cache = _TTLCache(ttl_seconds=60.0, max_entries=2)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x

        func(1)
        func(2)
        func(3)  # exceeds capacity → evict oldest (1)
        self.assertEqual(len(calls), 3)

        stats = cache.stats.snapshot()
        self.assertGreaterEqual(stats["evictions"], 1)

    def test_eviction_removes_stale_first(self):
        cache = _TTLCache(ttl_seconds=0.05, max_entries=2)
        calls = []

        @cache.decorator()
        def func(x):
            calls.append(x)
            return x

        func(1)
        import time

        time.sleep(0.1)  # entry 1 now stale
        func(2)
        func(3)  # at capacity, but 1 is stale → evict stale
        stats = cache.stats.snapshot()
        self.assertGreaterEqual(stats["evictions"], 1)


if __name__ == "__main__":
    unittest.main()
