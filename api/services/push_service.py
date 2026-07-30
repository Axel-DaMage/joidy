import json
import logging

from config import settings
from models.push_subscription import PushSubscription
from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def send_push_to_user(db: Session, user_id: int, title: str, body: str) -> None:
    """Send a Web Push notification to all subscriptions of a user."""

    if not settings.vapid_private_key:
        logger.warning("VAPID private key not configured; skipping push")
        return

    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": f"mailto:{settings.vapid_claim_email}"},
            )
        except WebPushException:
            logger.exception("Failed to send push to %s", sub.endpoint)
