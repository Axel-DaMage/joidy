"""Unit tests for push_service — WebPush wrapper.

Mocks the pywebpush.webpush HTTP call so no real network/FCM traffic occurs.
Covers successful send and failure (WebPushException) handling.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from database import Base
from models.push_subscription import PushSubscription
from pywebpush import WebPushException
from services.push_service import send_push_to_user
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class PushServiceTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._orig_key = settings.vapid_private_key
        self._orig_email = settings.vapid_claim_email
        settings.vapid_private_key = "test-vapid-key"
        settings.vapid_claim_email = "test@example.com"

    def tearDown(self) -> None:
        settings.vapid_private_key = self._orig_key
        settings.vapid_claim_email = self._orig_email
        self.engine.dispose()

    def _add_subscription(self, db, user_id=1):
        sub = PushSubscription(
            user_id=user_id,
            endpoint="https://fcm.googleapis.com/fcm/send/abc123",
            p256dh="p256dh-key",
            auth="auth-key",
        )
        db.add(sub)
        db.commit()
        return sub


class SendPushSuccessTest(PushServiceTestBase):
    @patch("services.push_service.webpush")
    def test_successful_push_to_single_subscription(self, mock_webpush):
        db = self.Session()
        self._add_subscription(db)

        send_push_to_user(db, user_id=1, title="Hello", body="World")

        mock_webpush.assert_called_once()
        call_kwargs = mock_webpush.call_args
        self.assertEqual(
            call_kwargs.kwargs["subscription_info"]["endpoint"],
            "https://fcm.googleapis.com/fcm/send/abc123",
        )
        import json

        self.assertEqual(json.loads(call_kwargs.kwargs["data"]), {"title": "Hello", "body": "World"})
        self.assertEqual(call_kwargs.kwargs["vapid_private_key"], "test-vapid-key")
        db.close()

    @patch("services.push_service.webpush")
    def test_successful_push_to_multiple_subscriptions(self, mock_webpush):
        db = self.Session()
        self._add_subscription(db, user_id=1)
        self._add_subscription(db, user_id=1)

        send_push_to_user(db, user_id=1, title="Hi", body="There")

        self.assertEqual(mock_webpush.call_count, 2)
        db.close()

    @patch("services.push_service.webpush")
    def test_no_subscriptions_does_not_call_webpush(self, mock_webpush):
        db = self.Session()
        send_push_to_user(db, user_id=999, title="Nope", body="Nobody")
        mock_webpush.assert_not_called()
        db.close()


class SendPushFailureTest(PushServiceTestBase):
    @patch("services.push_service.webpush")
    def test_webpush_exception_does_not_raise(self, mock_webpush):
        mock_webpush.side_effect = WebPushException("Boom", response=MagicMock())
        db = self.Session()
        self._add_subscription(db)

        # Should not raise — failure is logged, not propagated.
        send_push_to_user(db, user_id=1, title="Hi", body="Fail")
        mock_webpush.assert_called_once()
        db.close()

    @patch("services.push_service.webpush")
    def test_failure_on_one_sub_continues_to_next(self, mock_webpush):
        mock_webpush.side_effect = [
            WebPushException("first fails", response=MagicMock()),
            None,  # second succeeds
        ]
        db = self.Session()
        self._add_subscription(db, user_id=1)
        self._add_subscription(db, user_id=1)

        send_push_to_user(db, user_id=1, title="Hi", body="Mixed")
        self.assertEqual(mock_webpush.call_count, 2)
        db.close()


class SendPushNoVapidKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._orig_key = settings.vapid_private_key
        settings.vapid_private_key = ""

    def tearDown(self) -> None:
        settings.vapid_private_key = self._orig_key
        self.engine.dispose()

    @patch("services.push_service.webpush")
    def test_no_vapid_key_skips_push(self, mock_webpush):
        db = self.Session()
        sub = PushSubscription(
            user_id=1,
            endpoint="https://example.com/endpoint",
            p256dh="key",
            auth="auth",
        )
        db.add(sub)
        db.commit()

        send_push_to_user(db, user_id=1, title="Skip", body="Me")
        mock_webpush.assert_not_called()
        db.close()


if __name__ == "__main__":
    unittest.main()
