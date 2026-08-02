"""Unit tests for google_token_service — Fernet encryption/decryption roundtrip,
token storage, connection checks, and async token refresh logic (mocked HTTP).

This service is security-critical: it stores the OAuth refresh token encrypted
with Fernet derived from the app SECRET_KEY, and refreshes access tokens via
Google's token endpoint. Bugs here could leak refresh tokens or break Calendar/
Tasks integrations silently (#402).
"""

import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from database import Base
from models.google_token import GoogleToken
from services.google_token_service import (
    clear_tokens,
    decrypt_token,
    encrypt_token,
    get_stored_token,
    get_valid_access_token,
    is_connected,
    store_tokens,
)


class GoogleTokenTestBase(unittest.TestCase):
    """Base class with in-memory SQLite and a fixed SECRET_KEY for Fernet."""

    def setUp(self) -> None:
        self._orig_secret = settings.secret_key
        settings.secret_key = "test-secret-key-for-fernet-derivation"

        self._orig_client_id = settings.google_client_id
        self._orig_client_secret = settings.google_client_secret
        settings.google_client_id = "test-client-id"
        settings.google_client_secret = "test-client-secret"

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        settings.secret_key = self._orig_secret
        settings.google_client_id = self._orig_client_id
        settings.google_client_secret = self._orig_client_secret
        self.engine.dispose()


class TokenEncryptionTest(GoogleTokenTestBase):
    def test_encrypt_decrypt_roundtrip(self) -> None:
        original = "ya29.a0ARrdaM_refresh_secret_token_value"
        encrypted = encrypt_token(original)
        self.assertNotEqual(encrypted, original)
        self.assertEqual(decrypt_token(encrypted), original)

    def test_encrypt_produces_different_ciphertext(self) -> None:
        """Fernet includes a timestamp + IV, so encrypting the same token twice
        should yield different ciphertexts."""
        token = "my-refresh-token"
        c1 = encrypt_token(token)
        c2 = encrypt_token(token)
        self.assertNotEqual(c1, c2)
        # Both decrypt to the same plaintext.
        self.assertEqual(decrypt_token(c1), token)
        self.assertEqual(decrypt_token(c2), token)

    def test_decrypt_invalid_token_returns_none(self) -> None:
        self.assertIsNone(decrypt_token("not-a-valid-fernet-token"))

    def test_decrypt_garbage_bytes_returns_none(self) -> None:
        self.assertIsNone(decrypt_token(""))

    def test_decrypt_with_wrong_secret_returns_none(self) -> None:
        encrypted = encrypt_token("secret-refresh-token")
        # Change the secret key — decryption should fail closed.
        settings.secret_key = "a-completely-different-secret-key"
        self.assertIsNone(decrypt_token(encrypted))


class StoreTokensTest(GoogleTokenTestBase):
    def test_store_tokens_creates_row(self) -> None:
        with self.Session() as db:
            row = store_tokens(
                db,
                access_token="access-123",
                refresh_token="refresh-456",
                expires_in=3600,
            )
            self.assertEqual(row.user_id, 1)
            self.assertEqual(row.access_token, "access-123")
            self.assertIsNotNone(row.refresh_token_encrypted)
            self.assertNotEqual(row.refresh_token_encrypted, "refresh-456")
            self.assertEqual(row.token_type, "Bearer")
            self.assertIsNotNone(row.expires_at)

    def test_store_tokens_updates_existing_row(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="first-access",
                refresh_token="first-refresh",
                expires_in=3600,
            )
            row = store_tokens(
                db,
                access_token="second-access",
                refresh_token="second-refresh",
                expires_in=7200,
            )
            self.assertEqual(row.access_token, "second-access")
            # Only one row for user_id=1.
            self.assertEqual(db.query(GoogleToken).count(), 1)

    def test_store_tokens_without_refresh_keeps_old(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="first-access",
                refresh_token="first-refresh",
                expires_in=3600,
            )
            old_encrypted = get_stored_token(db).refresh_token_encrypted
            # Second store without refresh_token should not overwrite.
            store_tokens(
                db,
                access_token="second-access",
                refresh_token=None,
                expires_in=3600,
            )
            row = get_stored_token(db)
            self.assertEqual(row.access_token, "second-access")
            self.assertEqual(row.refresh_token_encrypted, old_encrypted)

    def test_store_tokens_sets_expiry(self) -> None:
        with self.Session() as db:
            before = datetime.now(timezone.utc)
            row = store_tokens(
                db,
                access_token="access",
                refresh_token="refresh",
                expires_in=3600,
            )
            after = datetime.now(timezone.utc)
            expected_min = before + timedelta(seconds=3600)
            expected_max = after + timedelta(seconds=3600)
            expires_at = row.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            self.assertGreaterEqual(expires_at, expected_min - timedelta(seconds=2))
            self.assertLessEqual(expires_at, expected_max + timedelta(seconds=2))


class IsConnectedTest(GoogleTokenTestBase):
    def test_not_connected_when_no_row(self) -> None:
        with self.Session() as db:
            self.assertFalse(is_connected(db))

    def test_not_connected_when_no_refresh_token(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="access",
                refresh_token=None,
                expires_in=3600,
            )
            self.assertFalse(is_connected(db))

    def test_connected_when_refresh_token_stored(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="access",
                refresh_token="refresh",
                expires_in=3600,
            )
            self.assertTrue(is_connected(db))


class ClearTokensTest(GoogleTokenTestBase):
    def test_clear_tokens_removes_row(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="access",
                refresh_token="refresh",
                expires_in=3600,
            )
            self.assertTrue(is_connected(db))
            clear_tokens(db)
            self.assertFalse(is_connected(db))
            self.assertIsNone(get_stored_token(db))

    def test_clear_tokens_no_row_is_noop(self) -> None:
        with self.Session() as db:
            # Should not raise when there's nothing to delete.
            clear_tokens(db)
            self.assertIsNone(get_stored_token(db))


class GetValidAccessTokenTest(GoogleTokenTestBase):
    """Tests for the async get_valid_access_token — HTTP calls are mocked."""

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_returns_none_when_not_connected(self) -> None:
        with self.Session() as db:
            result = self._run(get_valid_access_token(db))
            self.assertIsNone(result)

    def test_returns_none_when_no_refresh_token(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="access",
                refresh_token=None,
                expires_in=3600,
            )
            result = self._run(get_valid_access_token(db))
            self.assertIsNone(result)

    def test_returns_cached_token_when_still_valid(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="valid-access-token",
                refresh_token="refresh",
                expires_in=3600,
            )
            # Token expires in 1 hour, well beyond the 60s buffer.
            result = self._run(get_valid_access_token(db))
            self.assertEqual(result, "valid-access-token")

    def test_refreshes_expired_token(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="old-access",
                refresh_token="my-refresh",
                expires_in=-100,  # Already expired.
            )

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "access_token": "new-access-token",
                "expires_in": 3600,
            }

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch("services.google_token_service.httpx.AsyncClient", return_value=mock_client):
                result = self._run(get_valid_access_token(db))

            self.assertEqual(result, "new-access-token")
            # Verify the refresh request was made with correct payload.
            mock_client.post.assert_awaited_once()
            call_args = mock_client.post.call_args
            self.assertEqual(call_args.kwargs["data"]["grant_type"], "refresh_token")
            self.assertEqual(call_args.kwargs["data"]["refresh_token"], "my-refresh")
            self.assertEqual(call_args.kwargs["data"]["client_id"], "test-client-id")

            # DB should be updated with the new access token.
            row = get_stored_token(db)
            self.assertEqual(row.access_token, "new-access-token")

    def test_returns_none_on_http_error(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="old-access",
                refresh_token="my-refresh",
                expires_in=-100,
            )

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 400"))

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch("services.google_token_service.httpx.AsyncClient", return_value=mock_client):
                result = self._run(get_valid_access_token(db))

            self.assertIsNone(result)

    def test_returns_none_when_client_credentials_missing(self) -> None:
        settings.google_client_id = ""
        settings.google_client_secret = ""
        with self.Session() as db:
            store_tokens(
                db,
                access_token="old-access",
                refresh_token="my-refresh",
                expires_in=-100,
            )
            result = self._run(get_valid_access_token(db))
            self.assertIsNone(result)

    def test_returns_none_when_refresh_token_undecryptable(self) -> None:
        with self.Session() as db:
            store_tokens(
                db,
                access_token="old-access",
                refresh_token="my-refresh",
                expires_in=-100,
            )
            # Corrupt the encrypted refresh token.
            row = get_stored_token(db)
            row.refresh_token_encrypted = "corrupted-encrypted-data"
            db.commit()

            result = self._run(get_valid_access_token(db))
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
