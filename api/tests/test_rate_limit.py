"""Unit tests for middleware.rate_limit.UserRateLimiter (#1276, #1323).

Covers the strict-route IP bucketing (Bearer/XFF bypass fix), trusted-proxy
XFF handling, the /auth/login failure lockout, and the M-01 hardening:
bounded in-memory state and un-spoofable identity keys. The limiter is
exercised in isolation with lightweight request stubs — no TestClient needed.
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from middleware.rate_limit import UserLimit, UserRateLimiter


def _request(path="/notes/", ip="1.2.3.4", headers=None):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        client=SimpleNamespace(host=ip),
        headers=headers or {},
    )


class StrictRouteTests(unittest.TestCase):
    def setUp(self):
        self.limiter = UserRateLimiter(strict_requests_per_minute=5)

    def test_login_ignores_rotating_bearer(self):
        allowed = sum(
            self.limiter.check_rate_limit(_request(path="/auth/login", headers={"Authorization": f"Bearer tok{i}"}))[0]
            for i in range(50)
        )
        self.assertEqual(allowed, 5)

    def test_login_ignores_spoofed_xff(self):
        allowed = sum(
            self.limiter.check_rate_limit(_request(path="/auth/login", headers={"X-Forwarded-For": f"10.9.{i}.1"}))[0]
            for i in range(50)
        )
        self.assertEqual(allowed, 5)

    def test_strict_paths_cover_setup_and_webhooks(self):
        for path in ("/config/setup", "/webhook/obsidian", "/webhook/obsidian/legacy"):
            limiter = UserRateLimiter(strict_requests_per_minute=2)
            results = [limiter.check_rate_limit(_request(path=path))[0] for _ in range(3)]
            self.assertEqual(results, [True, True, False], path)

    def test_trailing_slash_is_strict(self):
        results = [self.limiter.check_rate_limit(_request(path="/auth/login/"))[0] for _ in range(6)]
        self.assertEqual(results, [True] * 5 + [False])

    def test_forged_bearer_tokens_share_ip_bucket(self):
        # Rotating unverifiable tokens must not escape into fresh
        # authenticated buckets — they collapse onto the caller's IP
        # bucket and exhaust the per-IP quota (#1323).
        limiter = UserRateLimiter(requests_per_minute=5)
        allowed = sum(
            limiter.check_rate_limit(_request(path="/notes/", headers={"Authorization": f"Bearer tok{i}"}))[0]
            for i in range(50)
        )
        self.assertEqual(allowed, 5)
        self.assertEqual(set(limiter._user_windows), {"ip:1.2.3.4"})


class TrustedProxyTests(unittest.TestCase):
    def test_xff_ignored_without_trusted_proxies(self):
        limiter = UserRateLimiter(requests_per_minute=3)
        results = [
            limiter.check_rate_limit(_request(ip="9.9.9.9", headers={"X-Forwarded-For": f"1.1.1.{i}"}))[0]
            for i in range(4)
        ]
        self.assertEqual(results, [True, True, True, False])

    def test_xff_ignored_for_untrusted_peer(self):
        limiter = UserRateLimiter(requests_per_minute=3, trusted_proxies="10.0.0.0/8")
        results = [
            limiter.check_rate_limit(_request(ip="9.9.9.9", headers={"X-Forwarded-For": f"1.1.1.{i}"}))[0]
            for i in range(4)
        ]
        self.assertEqual(results, [True, True, True, False])

    def test_xff_honored_for_trusted_peer(self):
        limiter = UserRateLimiter(requests_per_minute=2, trusted_proxies="10.0.0.0/8,127.0.0.1")
        # Different forwarded IPs behind the trusted peer → separate buckets.
        for i in range(4):
            ok, _ = limiter.check_rate_limit(_request(ip="10.0.0.5", headers={"X-Forwarded-For": f"203.0.113.{i}"}))
            self.assertTrue(ok)
        # Same forwarded IP → its own bucket fills at the per-IP limit.
        results = [
            limiter.check_rate_limit(_request(ip="10.0.0.5", headers={"X-Forwarded-For": "203.0.113.7"}))[0]
            for _ in range(3)
        ]
        self.assertEqual(results, [True, True, False])

    def test_non_ip_peer_never_trusted(self):
        # TestClient peers ("testclient") are not parseable IPs → XFF ignored.
        limiter = UserRateLimiter(requests_per_minute=2, trusted_proxies="0.0.0.0/0,::/0")
        results = [
            limiter.check_rate_limit(_request(ip="testclient", headers={"X-Forwarded-For": f"2.2.2.{i}"}))[0]
            for i in range(3)
        ]
        self.assertEqual(results, [True, True, False])


class LoginLockoutTests(unittest.TestCase):
    def setUp(self):
        self.limiter = UserRateLimiter(
            login_max_failures=3,
            login_lockout_base_seconds=60.0,
            login_lockout_max_seconds=3600.0,
        )
        self.login = _request(path="/auth/login")

    def test_no_lockout_below_threshold(self):
        for _ in range(2):
            self.limiter.record_login_result(self.login, 401)
        self.assertEqual(self.limiter.login_lock_remaining(self.login), 0.0)

    def test_lockout_at_threshold(self):
        for _ in range(3):
            self.limiter.record_login_result(self.login, 401)
        remaining = self.limiter.login_lock_remaining(self.login)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 60.0)

    def test_lockout_grows_exponentially(self):
        for _ in range(3):
            self.limiter.record_login_result(self.login, 401)
        first = self.limiter.login_lock_remaining(self.login)
        self.limiter.record_login_result(self.login, 401)
        second = self.limiter.login_lock_remaining(self.login)
        self.assertGreater(second, first)

    def test_success_resets_failures(self):
        for _ in range(3):
            self.limiter.record_login_result(self.login, 401)
        self.limiter.record_login_result(self.login, 200)
        self.assertEqual(self.limiter.login_lock_remaining(self.login), 0.0)
        self.limiter.record_login_result(self.login, 401)
        self.assertEqual(self.limiter.login_lock_remaining(self.login), 0.0)

    def test_non_401_error_does_not_count_or_reset(self):
        for _ in range(2):
            self.limiter.record_login_result(self.login, 401)
        self.limiter.record_login_result(self.login, 422)
        self.limiter.record_login_result(self.login, 401)
        self.assertGreater(self.limiter.login_lock_remaining(self.login), 0)

    def test_lockout_only_applies_to_login(self):
        webhook = _request(path="/webhook/obsidian")
        for _ in range(5):
            self.limiter.record_login_result(webhook, 401)
        self.assertEqual(self.limiter.login_lock_remaining(webhook), 0.0)
        self.assertEqual(self.limiter.login_lock_remaining(self.login), 0.0)

    def test_failures_are_per_ip(self):
        other = _request(path="/auth/login", ip="5.6.7.8")
        for _ in range(3):
            self.limiter.record_login_result(self.login, 401)
        self.assertGreater(self.limiter.login_lock_remaining(self.login), 0)
        self.assertEqual(self.limiter.login_lock_remaining(other), 0.0)

    def test_login_attempts_map_is_capped(self):
        # A spray of distinct source IPs must not grow _login_attempts past
        # its bound, even while every tracked lockout is still live (#1323).
        limiter = UserRateLimiter(max_login_attempts=5, login_max_failures=1)
        for i in range(10):
            limiter.record_login_result(_request(path="/auth/login", ip=f"10.0.0.{i}"), 401)
        self.assertLessEqual(len(limiter._login_attempts), 5)


def _jwt(sub: str, secret: str = "test-secret", exp_offset: float = 3600.0) -> str:
    return jwt.encode({"sub": sub, "exp": time.time() + exp_offset}, secret, algorithm="HS256")


class IdentityKeyTests(unittest.TestCase):
    """Authenticated buckets are keyed on *validated* identities (#1323)."""

    def test_valid_jwt_gets_user_bucket(self):
        limiter = UserRateLimiter()
        with patch("services.auth_service.signing_secret", return_value="test-secret"):
            identifier, limit = limiter._get_limit_for_request(
                _request(headers={"Authorization": f"Bearer {_jwt('7')}"})
            )
        self.assertEqual(identifier, "user:7")
        self.assertEqual(limit, limiter.auth_requests_per_minute)

    def test_expired_jwt_falls_back_to_ip(self):
        limiter = UserRateLimiter()
        with patch("services.auth_service.signing_secret", return_value="test-secret"):
            identifier, limit = limiter._get_limit_for_request(
                _request(headers={"Authorization": f"Bearer {_jwt('7', exp_offset=-10)}"})
            )
        self.assertEqual(identifier, "ip:1.2.3.4")
        self.assertEqual(limit, limiter.requests_per_minute)

    def test_wrong_signature_jwt_falls_back_to_ip(self):
        limiter = UserRateLimiter()
        forged = _jwt("7", secret="attacker-secret")
        with patch("services.auth_service.signing_secret", return_value="test-secret"):
            identifier, _ = limiter._get_limit_for_request(_request(headers={"Authorization": f"Bearer {forged}"}))
        self.assertEqual(identifier, "ip:1.2.3.4")

    def test_internal_service_token_gets_own_bucket(self):
        limiter = UserRateLimiter()
        with (
            patch("services.auth_service.signing_secret", return_value="test-secret"),
            patch("services.auth_service.verify_internal_token", return_value=True),
        ):
            identifier, limit = limiter._get_limit_for_request(
                _request(headers={"Authorization": "Bearer internal-token"})
            )
        self.assertEqual(identifier, "token:internal")
        self.assertEqual(limit, limiter.auth_requests_per_minute)

    def test_jwt_prefix_no_longer_collapses_buckets(self):
        # The old token[:15] key shared one bucket across all JWTs (common
        # 'eyJhbGciOiJIUzI' prefix); validated subs stay separate (#1323).
        limiter = UserRateLimiter()
        with patch("services.auth_service.signing_secret", return_value="test-secret"):
            first, _ = limiter._get_limit_for_request(_request(headers={"Authorization": f"Bearer {_jwt('1')}"}))
            second, _ = limiter._get_limit_for_request(_request(headers={"Authorization": f"Bearer {_jwt('2')}"}))
        self.assertEqual(first, "user:1")
        self.assertEqual(second, "user:2")

    def test_x_api_key_header_is_ignored(self):
        # X-API-Key is not an auth credential anywhere in the API; it must no
        # longer mint a fresh authenticated bucket per invented value (#1323).
        limiter = UserRateLimiter(requests_per_minute=5)
        allowed = sum(limiter.check_rate_limit(_request(headers={"X-API-Key": f"key-{i}"}))[0] for i in range(50))
        self.assertEqual(allowed, 5)
        self.assertEqual(set(limiter._user_windows), {"ip:1.2.3.4"})


class BoundedStateTests(unittest.TestCase):
    """_user_windows is an LRU with a hard cap and periodic sweep (#1323)."""

    def test_windows_lru_capped(self):
        limiter = UserRateLimiter(requests_per_minute=1000, max_windows=50)
        for i in range(200):
            limiter.check_rate_limit(_request(ip=f"10.1.{i // 256}.{i % 256}"))
        self.assertEqual(len(limiter._user_windows), 50)

    def test_lru_evicts_least_recently_used(self):
        limiter = UserRateLimiter(requests_per_minute=1000, max_windows=3)
        for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            limiter.check_rate_limit(_request(ip=ip))
        # Touch 1.1.1.1 → 2.2.2.2 becomes the LRU entry.
        limiter.check_rate_limit(_request(ip="1.1.1.1"))
        limiter.check_rate_limit(_request(ip="4.4.4.4"))
        self.assertIn("ip:1.1.1.1", limiter._user_windows)
        self.assertIn("ip:4.4.4.4", limiter._user_windows)
        self.assertNotIn("ip:2.2.2.2", limiter._user_windows)

    def test_periodic_sweep_reclaims_stale_windows(self):
        limiter = UserRateLimiter(requests_per_minute=1000, sweep_interval_seconds=30)
        stale = time.time() - 3600
        for i in range(10):
            limiter._user_windows[f"ip:10.0.0.{i}"] = UserLimit(requests=[stale])
        limiter._last_sweep = 0.0  # force the next check to sweep
        limiter.check_rate_limit(_request(ip="9.9.9.9"))
        self.assertEqual(set(limiter._user_windows), {"ip:9.9.9.9"})

    def test_sweep_throttled_by_interval(self):
        limiter = UserRateLimiter(requests_per_minute=1000, sweep_interval_seconds=3600)
        stale = time.time() - 3600
        limiter._user_windows["ip:8.8.8.8"] = UserLimit(requests=[stale])
        limiter._last_sweep = time.time()  # sweep not due yet
        limiter.check_rate_limit(_request(ip="9.9.9.9"))
        self.assertIn("ip:8.8.8.8", limiter._user_windows)

    def test_full_map_prefers_sweeping_dead_windows_over_lru(self):
        limiter = UserRateLimiter(requests_per_minute=1000, max_windows=3)
        stale = time.time() - 3600
        limiter._user_windows["ip:dead.1"] = UserLimit(requests=[stale])
        limiter._user_windows["ip:dead.2"] = UserLimit(requests=[stale])
        limiter._user_windows["ip:1.1.1.1"] = UserLimit(requests=[time.time()])
        # Map is full but two entries are dead: the live entry must survive.
        limiter.check_rate_limit(_request(ip="2.2.2.2"))
        self.assertIn("ip:1.1.1.1", limiter._user_windows)
        self.assertIn("ip:2.2.2.2", limiter._user_windows)
        self.assertNotIn("ip:dead.1", limiter._user_windows)


if __name__ == "__main__":
    unittest.main()
