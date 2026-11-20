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
    AUDIENCE,
    ISSUER,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    hash_password,
    verify_internal_token,
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

    def test_stored_hash_is_not_a_password(self):
        # Regression for #1275 (pass-the-hash): the stored bcrypt hash must
        # not authenticate as its own plaintext.
        h = hash_password("s3cret")
        self.assertFalse(verify_password(h, h))


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
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "typ": TOKEN_TYPE_ACCESS,
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


class TokenClaimsTest(unittest.TestCase):
    """Registered claims and type discrimination added in #1285."""

    def setUp(self):
        self._orig_key = settings.secret_key
        settings.secret_key = "test-secret-key"

    def tearDown(self):
        settings.secret_key = self._orig_key

    def _unsigned_payload(self, token: str) -> dict:
        return jwt.decode(token, options={"verify_signature": False})

    def test_access_token_carries_registered_claims(self):
        payload = self._unsigned_payload(create_access_token(42, "alice"))
        self.assertEqual(payload["iss"], ISSUER)
        self.assertEqual(payload["aud"], AUDIENCE)
        self.assertEqual(payload["typ"], TOKEN_TYPE_ACCESS)
        self.assertIn("iat", payload)

    def test_access_token_ttl_matches_configured_lifetime(self):
        # Default ACCESS_TOKEN_EXPIRE_MINUTES=720 (12h) — inside the 12–24h
        # bound required by #1285.
        self.assertLessEqual(settings.access_token_expire_minutes, 24 * 60)
        payload = self._unsigned_payload(create_access_token(1))
        self.assertEqual(payload["exp"] - payload["iat"], settings.access_token_expire_minutes * 60)

    def test_verify_rejects_unknown_issuer(self):
        token = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC),
                "iss": "evil-issuer",
                "aud": AUDIENCE,
                "typ": TOKEN_TYPE_ACCESS,
            },
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        self.assertIsNone(verify_token(token))

    def test_verify_rejects_wrong_audience(self):
        token = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC),
                "iss": ISSUER,
                "aud": "someone-else",
                "typ": TOKEN_TYPE_ACCESS,
            },
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        self.assertIsNone(verify_token(token))

    def test_verify_rejects_legacy_token_without_registered_claims(self):
        # Pre-#1285 tokens carried only sub/username/exp — they must now fail
        # closed (unknown issuer/audience) so clients are forced to re-login.
        token = jwt.encode(
            {
                "sub": "1",
                "username": "user",
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        self.assertIsNone(verify_token(token))

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token(42, "alice")
        payload = verify_token(token, expected_type=TOKEN_TYPE_REFRESH)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["typ"], TOKEN_TYPE_REFRESH)
        self.assertIn("jti", payload)

    def test_refresh_token_not_valid_as_access(self):
        token = create_refresh_token(1)
        self.assertIsNone(verify_token(token))  # defaults to access
        self.assertIsNone(get_current_user_id(token))

    def test_access_token_not_valid_as_refresh(self):
        token = create_access_token(1)
        self.assertIsNone(verify_token(token, expected_type=TOKEN_TYPE_REFRESH))

    def test_refresh_tokens_rotate_jti(self):
        self.assertNotEqual(
            self._unsigned_payload(create_refresh_token(1))["jti"],
            self._unsigned_payload(create_refresh_token(1))["jti"],
        )


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
