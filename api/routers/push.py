from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.push_subscription import PushSubscription
from pydantic import BaseModel
from services.auth_service import get_current_user
from services.push_service import send_push_to_user
from services.url_security import URLValidationError, validate_public_https_url
from sqlalchemy.orm import Session

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: dict


class PushMessageIn(BaseModel):
    title: str
    body: str


@router.get("/vapid-public-key")
def get_vapid_public_key(user_id: int = Depends(get_current_user)):
    # Return null instead of 503 when VAPID is not configured —
    # lets the frontend gracefully disable push notifications (#549)
    return {"publicKey": settings.vapid_public_key or None}


@router.post("/subscribe")
def subscribe(
    payload: SubscriptionIn,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    p256dh = payload.keys.get("p256dh")
    auth = payload.keys.get("auth")

    if not p256dh or not auth:
        raise HTTPException(status_code=422, detail="Missing push subscription keys")

    # SSRF guard (#1316): the endpoint is POSTed to by pywebpush, so only
    # accept https URLs whose host resolves to public IPs. Validated before
    # touching existing state so a rejected payload doesn't wipe the
    # current subscription.
    try:
        validate_public_https_url(payload.endpoint)
    except URLValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid endpoint URL: {exc}")

    # Remove any existing subscription for this user and create a new one.
    db.query(PushSubscription).filter(PushSubscription.user_id == user_id).delete()

    db.add(
        PushSubscription(
            user_id=user_id,
            endpoint=payload.endpoint,
            p256dh=p256dh,
            auth=auth,
        )
    )
    db.commit()
    return {"status": "ok"}


@router.post("/unsubscribe")
def unsubscribe(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    db.query(PushSubscription).filter(PushSubscription.user_id == user_id).delete()
    db.commit()
    return {"status": "ok"}


@router.post("/test")
def send_test_push(
    payload: PushMessageIn,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    send_push_to_user(db, user_id, payload.title, payload.body)
    return {"status": "ok"}
