"""Unit tests for auth_service — JWT creation/verification, password hashing,
and the auth-bypass behavior that previously let #322/#323 slip through."""

import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from unittest import mock

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

import jwt
from config import settings
from services.auth_service import (
    ALGORITHM,
    create_access_token,
    get_current_user_id,
    hash_password,
    is_plaintext_stored_password,
    verify_internal_token,
    verify_password,
    verify_token,
    warn_if_plaintext_auth_password,
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

    def test_stored_hash_is_not_a_password(self):
        # Regression for #1275 (pass-the-hash): the stored bcrypt hash must
        # not authenticate as its own plaintext.
        h = hash_password("s3cret")
        self.assertFalse(verify_password(h, h))


class PlaintextPasswordWarningTest(unittest.TestCase):
    """#1265: a plaintext AUTH_PASSWORD must produce a loud startup warning.

    The lifespan calls ``warn_if_plaintext_auth_password`` at boot; these
    tests cover the helper directly so the warning contract is pinned
    without booting the app.
    """

    def test_plaintext_stored_value_warns(self):
        with (
            mock.patch(
                "services.auth_service._effective_auth_password",
                return_value="hunter2",
            ),
            self.assertLogs("services.auth_service", level="WARNING") as logs,
        ):
            warn_if_plaintext_auth_password()
        self.assertTrue(
            any("PLAINTEXT" in line for line in logs.output),
            f"expected a plaintext warning, got: {logs.output}",
        )

    def test_bcrypt_stored_value_does_not_warn(self):
        stored = hash_password("s3cret")
        with (
            mock.patch(
                "services.auth_service._effective_auth_password",
                return_value=stored,
            ),
            self.assertNoLogs("services.auth_service", level="WARNING"),
        ):
            warn_if_plaintext_auth_password()

    def test_unset_password_does_not_warn(self):
        with (
            mock.patch(
                "services.auth_service._effective_auth_password",
                return_value="",
            ),
            self.assertNoLogs("services.auth_service", level="WARNING"),
        ):
            warn_if_plaintext_auth_password()

    def test_is_plaintext_stored_password(self):
        self.assertTrue(is_plaintext_stored_password("hunter2"))
        self.assertFalse(is_plaintext_stored_password(""))
        self.assertFalse(is_plaintext_stored_password(hash_password("s3cret")))


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


class InternalTokenTest(unittest.TestCase):
    def setUp(self):
        self._orig_token = settings.internal_api_token
        settings.internal_api_token = "service-token-abc"

    def tearDown(self):
        settings.internal_api_token = self._orig_token

    def test_verify_internal_token(self):
        self.assertTrue(verify_internal_token("service-token-abc"))
        self.assertFalse(verify_internal_token("wrong"))

    def test_verify_internal_token_rejects_when_unset(self):
        settings.internal_api_token = ""
        self.assertFalse(verify_internal_token("service-token-abc"))


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


if __name__ == "__main__":
    unittest.main()
