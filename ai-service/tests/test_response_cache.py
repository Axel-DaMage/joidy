"""Unit tests for response_cache.TTLCache and cache_key."""

import unittest

from response_cache import TTLCache, cache_key, get_cache


class TestTTLCache(unittest.TestCase):
    def test_set_and_get_roundtrip(self):
        cache = TTLCache(max_size=10, ttl_seconds=60)
        cache.set("k", [1.0, 2.0])
        self.assertEqual(cache.get("k"), [1.0, 2.0])

    def test_missing_key_returns_none(self):
        cache = TTLCache(max_size=10, ttl_seconds=60)
        self.assertIsNone(cache.get("nope"))

    def test_zero_ttl_expires_immediately(self):
        cache = TTLCache(max_size=10, ttl_seconds=0)
        cache.set("k", "v")
        self.assertIsNone(cache.get("k"))

    def test_expired_entry_is_removed(self):
        cache = TTLCache(max_size=10, ttl_seconds=0)
        cache.set("k", "v")
        cache.get("k")
        self.assertNotIn("k", cache._data)

    def test_evicts_oldest_when_full(self):
        cache = TTLCache(max_size=2, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.get("c"), 3)

    def test_get_refreshes_lru_order(self):
        cache = TTLCache(max_size=2, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # refresh "a" so "b" becomes oldest
        cache.set("c", 3)
        self.assertEqual(cache.get("a"), 1)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("c"), 3)

    def test_set_overwrites_existing_key(self):
        cache = TTLCache(max_size=10, ttl_seconds=60)
        cache.set("k", "old")
        cache.set("k", "new")
        self.assertEqual(cache.get("k"), "new")

    def test_clear_empties_cache(self):
        cache = TTLCache(max_size=10, ttl_seconds=60)
        cache.set("k", "v")
        cache.clear()
        self.assertIsNone(cache.get("k"))

    def test_max_size_floor_is_one(self):
        cache = TTLCache(max_size=0, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), 2)


class TestCacheKey(unittest.TestCase):
    def test_cache_key_deterministic(self):
        self.assertEqual(cache_key("embed", "model", "text"), cache_key("embed", "model", "text"))

    def test_cache_key_changes_with_parts(self):
        self.assertNotEqual(cache_key("embed", "m1", "text"), cache_key("embed", "m2", "text"))

    def test_cache_key_is_hex_sha256(self):
        key = cache_key("a", "b")
        self.assertEqual(len(key), 64)
        int(key, 16)  # raises if not hex


class TestGetCache(unittest.TestCase):
    def test_get_cache_returns_singleton(self):
        self.assertIs(get_cache(), get_cache())


if __name__ == "__main__":
    unittest.main()
