"""Unit tests for middleware.rate_limit.UserRateLimiter (#1276).

Covers the strict-route IP bucketing (Bearer/XFF bypass fix), trusted-proxy
XFF handling, and the /auth/login failure lockout. The limiter is exercised
in isolation with lightweight request stubs — no TestClient needed.
"""

import unittest
from types import SimpleNamespace

from middleware.rate_limit import UserRateLimiter


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

    def test_authenticated_routes_still_get_auth_bucket(self):
        allowed = sum(
            self.limiter.check_rate_limit(_request(path="/notes/", headers={"Authorization": f"Bearer tok{i}"}))[0]
            for i in range(50)
        )
        self.assertEqual(allowed, 50)  # each distinct token → 5000/min bucket


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


if __name__ == "__main__":
    unittest.main()
