"""Email inbox service — upsert/list/search for externally imported mail (n8n → Gmail)."""

from datetime import datetime
from typing import Any

from models.email_message import EmailMessage
from sqlalchemy import case as sa_case
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

MAX_BODY_TEXT = 50_000
MAX_SNIPPET = 2_000


def upsert_email(
    db: Session,
    user_id: int,
    *,
    account: str,
    gmail_id: str,
    thread_id: str | None = None,
    subject: str | None = None,
    sender: str | None = None,
    snippet: str | None = None,
    body_text: str | None = None,
    received_at: datetime | None = None,
    unread: bool = True,
    important: bool = False,
    importance_reason: str | None = None,
    labels: list | None = None,
) -> tuple[EmailMessage, bool]:
    """Create or update an inbox entry for (user_id, account, gmail_id).

    Returns ``(email, created)`` where ``created`` is True on first insert.
    Manual local state wins on re-sync — Gmail never learns about actions
    taken here, so for existing rows the sync result does not overwrite:
    ``unread`` keeps the value set from the UI (a pushed ``unread=True`` is
    only honored on creation) and ``important`` may be upgraded to True but
    never downgraded by the sync.
    """
    email = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.user_id == user_id,
            EmailMessage.account == account,
            EmailMessage.gmail_id == gmail_id,
        )
        .first()
    )
    created = email is None
    if created:
        email = EmailMessage(user_id=user_id, account=account, gmail_id=gmail_id)
        db.add(email)

    email.thread_id = thread_id
    email.subject = subject
    email.sender = sender
    email.snippet = (snippet or "")[:MAX_SNIPPET] if snippet else None
    email.body_text = (body_text or "")[:MAX_BODY_TEXT] if body_text else None
    email.received_at = received_at
    email.important = bool(important) or bool(email.important)
    email.importance_reason = importance_reason
    email.labels = labels if labels is not None else []
    if created:
        # A brand-new import follows the Gmail state (unread by definition).
        email.unread = unread

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        email = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.user_id == user_id,
                EmailMessage.account == account,
                EmailMessage.gmail_id == gmail_id,
            )
            .first()
        )
        if email is None:
            raise
        return email, False
    db.refresh(email)
    return email, created


def get_email(db: Session, user_id: int, email_id: int) -> EmailMessage | None:
    return db.query(EmailMessage).filter(EmailMessage.user_id == user_id, EmailMessage.id == email_id).first()


def _filtered_query(
    db: Session,
    user_id: int,
    *,
    unread: bool | None = None,
    important: bool | None = None,
    account: str | None = None,
    q: str | None = None,
) -> Any:
    query = db.query(EmailMessage).filter(EmailMessage.user_id == user_id)
    if unread is not None:
        query = query.filter(EmailMessage.unread == unread)
    if important is not None:
        query = query.filter(EmailMessage.important == important)
    if account:
        query = query.filter(EmailMessage.account == account)
    if q:
        like = f"%{q}%"
        query = query.filter(
            EmailMessage.subject.ilike(like) | EmailMessage.sender.ilike(like) | EmailMessage.snippet.ilike(like)
        )
    return query


def list_emails(
    db: Session,
    user_id: int,
    *,
    unread: bool | None = None,
    important: bool | None = None,
    account: str | None = None,
    q: str | None = None,
    limit: int = 100,
    skip: int = 0,
) -> list[EmailMessage]:
    """Unified inbox: merged accounts, newest first."""
    query = _filtered_query(db, user_id, unread=unread, important=important, account=account, q=q)
    return (
        query.order_by(EmailMessage.received_at.desc().nullslast(), EmailMessage.id.desc())
        .offset(max(skip, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )


def count_emails(
    db: Session,
    user_id: int,
    *,
    unread: bool | None = None,
    important: bool | None = None,
    account: str | None = None,
    q: str | None = None,
) -> int:
    """Total matching the same filters as ``list_emails`` (so ``total`` stays consistent)."""
    return _filtered_query(db, user_id, unread=unread, important=important, account=account, q=q).count()


def list_accounts(db: Session, user_id: int) -> list[dict]:
    """Distinct mailboxes with per-account counters (SQL aggregation)."""
    case = sa_case((EmailMessage.unread.is_(True), 1))
    rows = (
        db.query(
            EmailMessage.account,
            func.count(EmailMessage.id).label("total"),
            func.count(case).label("unread"),
            func.count(sa_case((EmailMessage.important.is_(True), 1))).label("important"),
        )
        .filter(EmailMessage.user_id == user_id)
        .group_by(EmailMessage.account)
        .order_by(EmailMessage.account)
        .all()
    )
    return [
        {"account": row.account, "total": row.total, "unread": row.unread, "important": row.important} for row in rows
    ]


def update_email_state(
    db: Session,
    user_id: int,
    email_id: int,
    *,
    unread: bool | None = None,
    important: bool | None = None,
    importance_reason: str | None = None,
) -> EmailMessage | None:
    """Manual state changes from the UI."""
    email = get_email(db, user_id, email_id)
    if email is None:
        return None
    if unread is not None:
        email.unread = unread
    if important is not None:
        email.important = important
    if importance_reason is not None:
        email.importance_reason = importance_reason
    db.commit()
    db.refresh(email)
    return email


def delete_email(db: Session, user_id: int, email_id: int) -> bool:
    email = get_email(db, user_id, email_id)
    if email is None:
        return False
    db.delete(email)
    db.commit()
    return True
