"""At-rest encryption parity tests (#1286, #1329).

Verifies the shared ``encryption`` module and that every ``EncryptedText``
column writes Fernet ciphertext to the DB while the ORM transparently
returns plaintext — plus the lazy-migration passthrough for rows written
before encryption landed. Security-critical: a regression here silently
stores OAuth tokens or webhook secrets in cleartext.
"""

import sys
import types
import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from database import Base
from encryption import decrypt_str, decrypt_str_or_plaintext, encrypt_str
from models.github import GitHubRepo
from models.google_calendar_event import GoogleCalendarEvent
from models.google_calendar_sync import GoogleCalendarSyncState
from models.google_token import GoogleToken
from models.push_subscription import PushSubscription
from services.google_token_service import store_tokens


class FieldEncryptionTestBase(unittest.TestCase):
    """In-memory SQLite + a fixed SECRET_KEY for the Fernet derivation."""

    def setUp(self) -> None:
        self._orig_secret = settings.secret_key
        settings.secret_key = "test-secret-key-for-fernet-derivation"
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        settings.secret_key = self._orig_secret
        self.engine.dispose()

    def _raw(self, db, sql: str, **params):
        """Bypass the ORM so we see what's actually stored on disk."""
        return db.execute(text(sql), params).scalar()

    def _assert_ciphertext(self, stored: str, plaintext: str) -> None:
        self.assertIsNotNone(stored)
        self.assertNotEqual(stored, plaintext)
        # Fernet tokens are urlsafe-base64 starting with the version byte 0x80.
        self.assertTrue(stored.startswith("gAAAA"), f"expected Fernet ciphertext, got {stored[:20]!r}")


class HelperFunctionsTest(FieldEncryptionTestBase):
    def test_encrypt_decrypt_roundtrip(self) -> None:
        ciphertext = encrypt_str("sensitive-value")
        self.assertNotEqual(ciphertext, "sensitive-value")
        self.assertEqual(decrypt_str(ciphertext), "sensitive-value")

    def test_decrypt_invalid_returns_none(self) -> None:
        self.assertIsNone(decrypt_str("not-a-fernet-token"))

    def test_decrypt_or_plaintext_handles_legacy_values(self) -> None:
        # Rows written before encryption read back as-is (lazy migration).
        self.assertEqual(decrypt_str_or_plaintext("legacy-plaintext"), "legacy-plaintext")
        ciphertext = encrypt_str("new-value")
        self.assertEqual(decrypt_str_or_plaintext(ciphertext), "new-value")

    def test_wrong_key_fails_closed(self) -> None:
        ciphertext = encrypt_str("secret")
        settings.secret_key = "a-different-secret-key"
        self.assertIsNone(decrypt_str(ciphertext))


class GoogleTokenEncryptionTest(FieldEncryptionTestBase):
    def test_access_token_is_ciphertext_at_rest(self) -> None:
        with self.Session() as db:
            store_tokens(db, access_token="ya29.live-access-token", refresh_token="refresh-1", expires_in=3600)
            self._assert_ciphertext(
                self._raw(db, "SELECT access_token FROM google_tokens WHERE user_id = 1"),
                "ya29.live-access-token",
            )

    def test_access_token_decrypts_on_read(self) -> None:
        with self.Session() as db:
            row = store_tokens(db, access_token="ya29.live-access-token", refresh_token="refresh-1", expires_in=3600)
            self.assertEqual(row.access_token, "ya29.live-access-token")
            # Re-load through the ORM to prove transparent decryption.
            db.expire_all()
            self.assertEqual(
                db.query(GoogleToken).filter(GoogleToken.user_id == 1).one().access_token,
                "ya29.live-access-token",
            )

    def test_legacy_plaintext_access_token_still_reads(self) -> None:
        with self.Session() as db:
            db.execute(
                text(
                    "INSERT INTO google_tokens (user_id, access_token, token_type) "
                    "VALUES (1, 'ya29.pre-encryption-token', 'Bearer')"
                )
            )
            db.commit()
            row = db.query(GoogleToken).filter(GoogleToken.user_id == 1).one()
            self.assertEqual(row.access_token, "ya29.pre-encryption-token")


class GitHubWebhookSecretEncryptionTest(FieldEncryptionTestBase):
    def test_webhook_secret_is_ciphertext_at_rest(self) -> None:
        with self.Session() as db:
            db.add(
                GitHubRepo(
                    name="repo",
                    full_name="owner/repo",
                    url="https://github.com/owner/repo",
                    webhook_secret="a" * 64,
                )
            )
            db.commit()
            self._assert_ciphertext(
                self._raw(db, "SELECT webhook_secret FROM github_repos WHERE full_name = 'owner/repo'"),
                "a" * 64,
            )
            db.expire_all()
            self.assertEqual(db.query(GitHubRepo).one().webhook_secret, "a" * 64)


class PushSubscriptionEncryptionTest(FieldEncryptionTestBase):
    def test_subscription_fields_are_ciphertext_at_rest(self) -> None:
        with self.Session() as db:
            db.add(
                PushSubscription(
                    user_id=1,
                    endpoint="https://push.example.com/sub/abc123",
                    p256dh="BP256DHKEY",
                    auth="auth-secret",
                )
            )
            db.commit()
            for col, plaintext in (
                ("endpoint", "https://push.example.com/sub/abc123"),
                ("p256dh", "BP256DHKEY"),
                ("auth", "auth-secret"),
            ):
                self._assert_ciphertext(
                    self._raw(db, f"SELECT {col} FROM push_subscriptions WHERE user_id = 1"),
                    plaintext,
                )
            db.expire_all()
            sub = db.query(PushSubscription).one()
            self.assertEqual(sub.endpoint, "https://push.example.com/sub/abc123")
            self.assertEqual(sub.p256dh, "BP256DHKEY")
            self.assertEqual(sub.auth, "auth-secret")


class GoogleCalendarEncryptionTest(FieldEncryptionTestBase):
    def test_event_content_is_ciphertext_at_rest(self) -> None:
        with self.Session() as db:
            db.add(
                GoogleCalendarEvent(
                    user_id=1,
                    calendar_id="primary",
                    google_id="ev-1",
                    summary="Dentist appointment",
                    description="Bring insurance card",
                    location="Calle Falsa 123",
                    start_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                )
            )
            db.commit()
            for col, plaintext in (
                ("summary", "Dentist appointment"),
                ("description", "Bring insurance card"),
                ("location", "Calle Falsa 123"),
            ):
                self._assert_ciphertext(
                    self._raw(db, f"SELECT {col} FROM google_calendar_events WHERE google_id = 'ev-1'"),
                    plaintext,
                )
            db.expire_all()
            self.assertEqual(db.query(GoogleCalendarEvent).one().summary, "Dentist appointment")

    def test_sync_token_is_ciphertext_at_rest(self) -> None:
        with self.Session() as db:
            db.add(
                GoogleCalendarSyncState(
                    user_id=1,
                    calendar_id="primary",
                    sync_token="CNnVj_test-sync-token",
                )
            )
            db.commit()
            self._assert_ciphertext(
                self._raw(
                    db,
                    "SELECT sync_token FROM google_calendar_sync_state WHERE calendar_id = 'primary'",
                ),
                "CNnVj_test-sync-token",
            )
            db.expire_all()
            self.assertEqual(
                db.query(GoogleCalendarSyncState).one().sync_token,
                "CNnVj_test-sync-token",
            )


if __name__ == "__main__":
    unittest.main()
