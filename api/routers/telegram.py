"""Telegram bot webhook router (#1132).

Receives Telegram Bot API updates on ``POST /telegram/webhook`` and hands
them to ``services.telegram_service`` for command → CRUD translation.
The webhook is intentionally unauthenticated (Telegram servers call it);
access is controlled by two optional layers:

- ``TELEGRAM_WEBHOOK_SECRET`` — verified against the
  ``X-Telegram-Bot-Api-Secret-Token`` header Telegram sends when the
  webhook is registered with a ``secret_token``.
- ``TELEGRAM_ALLOWED_USER_ID`` — sender allow-list enforced in the service.

The management endpoints (``/telegram/status``, ``/telegram/webhook``
PUT/DELETE for registering the URL with Telegram) do require the app JWT.
"""

import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from services import telegram_service
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/telegram", tags=["telegram"])

SECRET_HEADER = "x-telegram-bot-api-secret-token"


class WebhookUrl(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def https_only(cls, v: str) -> str:
        v = v.strip()
        # Telegram only delivers webhooks over HTTPS on ports 443/80/88/8443.
        if not v.startswith("https://"):
            raise ValueError("webhook url must be https://")
        if len(v) > 2048:
            raise ValueError("webhook url is too long")
        return v


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive a Telegram update. Always answers 200 once authenticated by
    secret so Telegram does not retry deliveries we already processed."""
    if not telegram_service.is_configured():
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")
    if not telegram_service.verify_webhook_secret(request.headers.get(SECRET_HEADER)):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Invalid update payload")

    result = await telegram_service.handle_update(db, update)
    return {"ok": True, **result}


@router.get("/status")
def telegram_status(user: dict = Depends(get_current_user)):
    """Report whether the bot is configured (no secrets disclosed)."""
    return {
        "configured": telegram_service.is_configured(),
        "allowed_user_restricted": telegram_service.is_user_restricted(),
        "webhook_secret_set": bool(settings.telegram_webhook_secret),
    }


@router.put("/webhook")
async def register_webhook(
    data: WebhookUrl,
    user: dict = Depends(get_current_user),
):
    """Register ``url`` as the Telegram webhook via ``setWebhook``.

    Sends ``TELEGRAM_WEBHOOK_SECRET`` as ``secret_token`` when configured so
    incoming updates carry it in the secret header.
    """
    try:
        return await telegram_service.set_webhook(data.url)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Telegram setWebhook failed")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Telegram API unreachable")


@router.delete("/webhook")
async def unregister_webhook(user: dict = Depends(get_current_user)):
    """Remove the registered Telegram webhook."""
    try:
        return await telegram_service.delete_webhook()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Telegram API unreachable")
