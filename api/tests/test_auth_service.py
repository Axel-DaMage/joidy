"""Unit tests for auth_service — JWT creation/verification, password hashing,
and the auth-bypass behavior that previously let #322/#323 slip through."""

import sys
import types
import unittest
from datetime import UTC, datetime, timedelta

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

import jwt
from config import settings
from services.auth_service import (
    ALGORITHM,
    _is_loopback,
    create_access_token,
    get_current_user_id,
    hash_password,
    verify_password,
    verify_token,
)


class PasswordTest(unittest.TestCase):
    def test_hash_and_verify_roundtrip(self):
        h = hash_password("s3cret")
        self.assertTrue(h.startswith("$2b$"))
        self.assertTrue(verify_password("s3cret", h))
        self.assertFalse(verify_password("wrong", h))

    def test_verify_plaintext_backward_compat(self):
        # Stored plaintext (legacy) still verifies with exact match.
        self.assertTrue(verify_password("plain", "plain"))
        self.assertFalse(verify_password("plain", "other"))


class TokenTest(unittest.TestCase):
    def setUp(self):
        self._orig_key = settings.secret_key
        settings.secret_key = "test-secret-key"

    def tearDown(self):
        settings.secret_key = self._orig_key

    def test_create_and_verify_token(self):
        token = create_access_token(42, "alice")
        payload = verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(get_current_user_id(token), 42)

    def test_create_token_without_secret_raises(self):
        settings.secret_key = ""
        with self.assertRaises(ValueError):
            create_access_token(1)

    def test_verify_expired_token_returns_none(self):
        # Build a token that expired in the past.
        payload = {
            "sub": "5",
            "username": "bob",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        self.assertIsNone(verify_token(token))
        self.assertIsNone(get_current_user_id(token))

    def test_verify_invalid_token_returns_none(self):
        self.assertIsNone(verify_token("not.a.jwt"))
        self.assertIsNone(get_current_user_id("not.a.jwt"))

    def test_verify_token_wrong_secret_returns_none(self):
        token = create_access_token(7)
        # Verify against a different secret.
        self.assertIsNone(verify_token(token + "x"))


class NoSecretKeyTest(unittest.TestCase):
    def setUp(self):
        self._orig_key = settings.secret_key
        settings.secret_key = ""

    def tearDown(self):
        settings.secret_key = self._orig_key

    def test_verify_token_skipped_without_secret(self):
        # Without a secret key, verification must fail closed (return None),
        # never accept a forged token.
        self.assertIsNone(verify_token("anything"))


class LoopbackCheckTest(unittest.TestCase):
    """#1282: the dev bypass is loopback-only; the check must fail closed on
    anything that is not a literal loopback IP."""

    def test_loopback_ips_accepted(self):
        for host in ("127.0.0.1", "127.0.0.2", "127.255.255.254", "::1", "::ffff:127.0.0.1"):
            self.assertTrue(_is_loopback(host), host)

    def test_non_loopback_ips_rejected(self):
        for host in ("192.168.1.10", "10.0.0.8", "172.16.0.5", "203.0.113.7", "fe80::1"):
            self.assertFalse(_is_loopback(host), host)

    def test_ipv4_mapped_non_loopback_rejected(self):
        # ::ffff:10.0.0.5 unwraps to 10.0.0.5 — must not smuggle in as IPv6.
        self.assertFalse(_is_loopback("::ffff:10.0.0.5"))
        self.assertTrue(_is_loopback("::ffff:127.0.0.1"))

    def test_non_ip_values_fail_closed(self):
        # The TestClient default peer, hostnames and empty values are not
        # loopback IPs — deny rather than guess.
        for host in ("testclient", "localhost", "", None):
            self.assertFalse(_is_loopback(host), host)


if __name__ == "__main__":
    unittest.main()
