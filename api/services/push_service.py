import json
import logging

from config import settings
from models.push_subscription import PushSubscription
from pywebpush import WebPushException, webpush
from services.url_security import URLValidationError, validate_public_https_url
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def send_push_to_user(db: Session, user_id: int, title: str, body: str) -> None:
    """Send a Web Push notification to all subscriptions of a user."""

    if not settings.vapid_private_key:
        logger.warning("VAPID private key not configured; skipping push")
        return

    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()

    for sub in subs:
        # Re-resolve at send time (#1316): DNS answers can change between
        # subscribe and send (rebinding), so a stored endpoint is never
        # trusted blindly.
        try:
            validate_public_https_url(sub.endpoint)
        except URLValidationError as exc:
            logger.warning("Skipping push to %s: %s", sub.endpoint, exc)
            continue
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
