from datetime import datetime

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models.email_message import EmailMessage
from pydantic import BaseModel, Field, field_validator
from services.auth_service import get_current_user
from services.email_service import (
    count_emails,
    delete_email,
    list_accounts,
    list_emails,
    update_email_state,
    upsert_email,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/emails", tags=["emails"])


class EmailUpsert(BaseModel):
    """Message pushed by the n8n Gmail sync workflow (upsert semantics)."""

    account: str = Field(min_length=3, max_length=255)
    gmail_id: str = Field(min_length=1, max_length=64)
    thread_id: str | None = Field(default=None, max_length=64)
    subject: str | None = None
    sender: str | None = Field(default=None, max_length=320)
    snippet: str | None = None
    body_text: str | None = None
    received_at: str | None = None
    unread: bool = True
    important: bool = False
    importance_reason: str | None = Field(default=None, max_length=255)
    labels: list[str] = Field(default_factory=list)

    @field_validator("gmail_id", "account")
    @classmethod
    def strip_ids(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class EmailPatch(BaseModel):
    unread: bool | None = None
    important: bool | None = None
    importance_reason: str | None = Field(default=None, max_length=255)


def _parse_received_at(value: str | None) -> object:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="received_at must be an ISO 8601 datetime")


def _serialize_email(email: EmailMessage) -> dict:
    return {
        "id": email.id,
        "account": email.account,
        "gmail_id": email.gmail_id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender": email.sender,
        "snippet": email.snippet,
        "received_at": email.received_at.isoformat() if email.received_at else None,
        "unread": email.unread,
        "important": email.important,
        "importance_reason": email.importance_reason,
        "labels": email.labels or [],
        "created_at": email.created_at.isoformat() if email.created_at else None,
        "updated_at": email.updated_at.isoformat() if email.updated_at else None,
    }


@router.get("/")
def list_inbox(
    unread: bool | None = Query(default=None),
    important: bool | None = Query(default=None),
    account: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Unified inbox: all accounts merged, newest first."""
    emails = list_emails(db, user_id, unread=unread, important=important, account=account, q=q, limit=limit, skip=skip)
    total = count_emails(db, user_id, unread=unread, important=important)
    return {"items": [_serialize_email(e) for e in emails], "total": total}


@router.get("/accounts")
def list_inbox_accounts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Linked mailboxes with per-account unread/important counters."""
    return list_accounts(db, user_id)


@router.post("/", status_code=201)
def push_email(
    data: EmailUpsert,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Upsert one message (idempotent per account+gmail_id)."""
    received_at = _parse_received_at(data.received_at)
    email, created = upsert_email(
        db,
        user_id,
        account=data.account,
        gmail_id=data.gmail_id,
        thread_id=data.thread_id,
        subject=data.subject,
        sender=data.sender,
        snippet=data.snippet,
        body_text=data.body_text,
        received_at=received_at,  # type: ignore[arg-type]
        unread=data.unread,
        important=data.important,
        importance_reason=data.importance_reason,
        labels=data.labels,
    )
    serialized = _serialize_email(email)
    serialized["created"] = created
    return serialized


@router.patch("/{email_id}")
def patch_email(
    email_id: int,
    data: EmailPatch,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Mark read/unread or (un)mark important."""
    email = update_email_state(
        db,
        user_id,
        email_id,
        unread=data.unread,
        important=data.important,
        importance_reason=data.importance_reason,
    )
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return _serialize_email(email)


@router.delete("/{email_id}", status_code=204)
def remove_email(
    email_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Archive (remove from the local inbox view only — the mailbox is untouched)."""
    if not delete_email(db, user_id, email_id):
        raise HTTPException(status_code=404, detail="Email not found")
