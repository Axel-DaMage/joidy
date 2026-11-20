"""Unit tests for integration_token_service — provider-agnostic OAuth token
storage (#44, reusable for Spotify #45).

Security-critical: tokens are Fernet-encrypted at rest (same scheme as
``google_token_service``/#1286), one row per provider, and access tokens
refresh transparently — persisting rotated refresh tokens (Strava invalidates
the old one on every refresh). Bugs here leak credentials or break every
OAuth integration silently.
"""

import asyncio
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from database import Base
from models.integration_token import IntegrationToken
from services import integration_token_service as its


class IntegrationTokenTestBase(unittest.TestCase):
    """Base class with in-memory SQLite and a fixed SECRET_KEY for Fernet."""

    def setUp(self) -> None:
        self._orig_secret = settings.secret_key
        settings.secret_key = "test-secret-key-for-fernet-derivation"

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        settings.secret_key = self._orig_secret
        self.engine.dispose()

    def _run(self, coro):
        return asyncio.run(coro)


class TokenEncryptionTest(IntegrationTokenTestBase):
    def test_encrypt_decrypt_roundtrip(self) -> None:
        original = "strava-refresh-token-secret"
        encrypted = its.encrypt_token(original)
        self.assertNotEqual(encrypted, original)
        self.assertEqual(its.decrypt_token(encrypted), original)

    def test_encrypt_produces_different_ciphertext(self) -> None:
        c1 = its.encrypt_token("same-token")
        c2 = its.encrypt_token("same-token")
        self.assertNotEqual(c1, c2)
        self.assertEqual(its.decrypt_token(c1), "same-token")
        self.assertEqual(its.decrypt_token(c2), "same-token")

    def test_decrypt_invalid_token_returns_none(self) -> None:
        self.assertIsNone(its.decrypt_token("not-a-valid-fernet-token"))
        self.assertIsNone(its.decrypt_token(""))

    def test_decrypt_with_wrong_secret_returns_none(self) -> None:
        encrypted = its.encrypt_token("secret-refresh-token")
        settings.secret_key = "a-completely-different-secret-key"
        self.assertIsNone(its.decrypt_token(encrypted))


class StoreTokensTest(IntegrationTokenTestBase):
    def test_store_tokens_creates_row_per_provider(self) -> None:
        with self.Session() as db:
            strava = its.store_tokens(
                db,
                its.PROVIDER_STRAVA,
                access_token="strava-access",
                refresh_token="strava-refresh",
                expires_in=3600,
                account_id="12345",
            )
            self.assertEqual(strava.provider, "strava")
            self.assertEqual(strava.access_token, "strava-access")
            self.assertIsNotNone(strava.refresh_token_encrypted)
            self.assertNotEqual(strava.refresh_token_encrypted, "strava-refresh")
            self.assertEqual(strava.account_id, "12345")
            self.assertIsNotNone(strava.expires_at)

            # A second provider gets its own row — no schema change needed (#45).
            spotify = its.store_tokens(
                db,
                its.PROVIDER_SPOTIFY,
                access_token="spotify-access",
                refresh_token="spotify-refresh",
                expires_in=3600,
            )
            self.assertEqual(spotify.provider, "spotify")
            self.assertEqual(db.query(IntegrationToken).count(), 2)

    def test_store_tokens_updates_existing_provider_row(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="first", refresh_token="r1", expires_in=3600)
            its.store_tokens(db, its.PROVIDER_SPOTIFY, access_token="spotify", refresh_token="sr", expires_in=3600)
            row = its.store_tokens(db, its.PROVIDER_STRAVA, access_token="second", refresh_token="r2", expires_in=7200)
            self.assertEqual(row.access_token, "second")
            self.assertEqual(db.query(IntegrationToken).filter_by(provider="strava").count(), 1)
            self.assertEqual(db.query(IntegrationToken).count(), 2)

    def test_store_tokens_without_refresh_keeps_old(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="first", refresh_token="r1", expires_in=3600)
            stored = its.get_stored_token(db, its.PROVIDER_STRAVA)
            assert stored is not None and stored.refresh_token_encrypted is not None
            old_encrypted = stored.refresh_token_encrypted
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="second", refresh_token=None, expires_in=3600)
            row = its.get_stored_token(db, its.PROVIDER_STRAVA)
            assert row is not None
            self.assertEqual(row.access_token, "second")
            self.assertEqual(row.refresh_token_encrypted, old_encrypted)

    def test_access_token_encrypted_at_rest(self) -> None:
        """Raw SQL must show Fernet ciphertext, never the plaintext token."""
        with self.Session() as db:
            its.store_tokens(
                db,
                its.PROVIDER_STRAVA,
                access_token="PLAINTEXT-ACCESS",
                refresh_token="PLAINTEXT-REFRESH",
                expires_in=3600,
            )
            raw_access = db.execute(
                text("SELECT access_token FROM integration_tokens WHERE provider = 'strava'")
            ).scalar()
            raw_refresh = db.execute(
                text("SELECT refresh_token_encrypted FROM integration_tokens WHERE provider = 'strava'")
            ).scalar()
            assert raw_access is not None and raw_refresh is not None
            self.assertTrue(raw_access.startswith("gAAAA"))
            self.assertTrue(raw_refresh.startswith("gAAAA"))
            self.assertNotIn("PLAINTEXT", raw_access)
            self.assertNotIn("PLAINTEXT", raw_refresh)

    def test_store_tokens_absolute_expiry(self) -> None:
        with self.Session() as db:
            expiry = datetime.now(UTC) + timedelta(hours=2)
            row = its.store_tokens(
                db,
                its.PROVIDER_STRAVA,
                access_token="access",
                refresh_token="refresh",
                expires_at=expiry,
            )
            stored = row.expires_at
            assert stored is not None
            if stored.tzinfo is None:
                stored = stored.replace(tzinfo=UTC)
            self.assertAlmostEqual(stored.timestamp(), expiry.timestamp(), delta=2)


class ConnectionStateTest(IntegrationTokenTestBase):
    def test_is_connected_states(self) -> None:
        with self.Session() as db:
            self.assertFalse(its.is_connected(db, its.PROVIDER_STRAVA))
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="a", refresh_token=None, expires_in=3600)
            self.assertFalse(its.is_connected(db, its.PROVIDER_STRAVA))
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="a", refresh_token="r", expires_in=3600)
            self.assertTrue(its.is_connected(db, its.PROVIDER_STRAVA))
            # Provider isolation: spotify row does not mark strava connected.
            self.assertFalse(its.is_connected(db, its.PROVIDER_SPOTIFY))

    def test_clear_tokens(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="a", refresh_token="r", expires_in=3600)
            its.clear_tokens(db, its.PROVIDER_STRAVA)
            self.assertIsNone(its.get_stored_token(db, its.PROVIDER_STRAVA))
            its.clear_tokens(db, its.PROVIDER_STRAVA)  # no-op, must not raise


class GetValidAccessTokenTest(IntegrationTokenTestBase):
    """Refresh logic with an injected refresher — no HTTP needed."""

    def test_returns_none_when_not_connected(self) -> None:
        with self.Session() as db:
            refresher = AsyncMock()
            self.assertIsNone(self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher)))
            refresher.assert_not_awaited()

    def test_returns_cached_token_when_valid(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="cached-access", refresh_token="r", expires_in=3600)
            refresher = AsyncMock()
            result = self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher))
            self.assertEqual(result, "cached-access")
            refresher.assert_not_awaited()

    def test_refreshes_within_expiry_buffer(self) -> None:
        """A token expiring in <60s is refreshed proactively (clock-skew guard)."""
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="old", refresh_token="r", expires_in=30)
            refresher = AsyncMock(return_value={"access_token": "fresh", "expires_in": 3600})
            result = self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher))
            self.assertEqual(result, "fresh")
            refresher.assert_awaited_once_with("r")

    def test_refreshes_expired_token_and_persists_rotation(self) -> None:
        with self.Session() as db:
            its.store_tokens(
                db, its.PROVIDER_STRAVA, access_token="old-access", refresh_token="old-refresh", expires_in=-100
            )
            refresher = AsyncMock(
                return_value={
                    "access_token": "new-access",
                    "refresh_token": "rotated-refresh",  # Strava rotates on every refresh
                    "expires_in": 3600,
                    "account_id": "12345",
                }
            )
            result = self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher))

            self.assertEqual(result, "new-access")
            refresher.assert_awaited_once_with("old-refresh")
            row = its.get_stored_token(db, its.PROVIDER_STRAVA)
            assert row is not None
            self.assertEqual(row.access_token, "new-access")
            assert row.refresh_token_encrypted is not None
            self.assertEqual(its.decrypt_token(row.refresh_token_encrypted), "rotated-refresh")
            self.assertEqual(row.account_id, "12345")
            self.assertIsNotNone(row.expires_at)

    def test_refresh_without_new_refresh_token_keeps_old(self) -> None:
        """Providers that do NOT rotate (e.g. Google) may omit refresh_token."""
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="old", refresh_token="keep-me", expires_in=-100)
            refresher = AsyncMock(return_value={"access_token": "new", "expires_in": 3600})
            result = self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher))
            self.assertEqual(result, "new")
            row = its.get_stored_token(db, its.PROVIDER_STRAVA)
            assert row is not None and row.refresh_token_encrypted is not None
            self.assertEqual(its.decrypt_token(row.refresh_token_encrypted), "keep-me")

    def test_returns_none_when_refresher_fails(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="old", refresh_token="r", expires_in=-100)
            refresher = AsyncMock(side_effect=RuntimeError("token endpoint down"))
            self.assertIsNone(self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher)))

    def test_returns_none_when_refresher_returns_no_access_token(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="old", refresh_token="r", expires_in=-100)
            refresher = AsyncMock(return_value={"refresh_token": "rotated"})
            self.assertIsNone(self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher)))

    def test_returns_none_when_refresh_token_undecryptable(self) -> None:
        with self.Session() as db:
            its.store_tokens(db, its.PROVIDER_STRAVA, access_token="old", refresh_token="r", expires_in=-100)
            row = its.get_stored_token(db, its.PROVIDER_STRAVA)
            assert row is not None
            row.refresh_token_encrypted = "corrupted-ciphertext"
            db.commit()
            refresher = AsyncMock()
            self.assertIsNone(self._run(its.get_valid_access_token(db, its.PROVIDER_STRAVA, refresher)))
            refresher.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
