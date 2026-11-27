"""Publish joidy calendar tasks to Google Calendar as all-day events.

Every scheduled task (``date`` set) is mirrored to the user's primary
calendar as a single all-day event titled after the task, colored with the
Google palette entry closest to the task's own color (or its priority when
no custom color is set). Done tasks render transparent. Google Tasks were
considered but rejected: the OAuth flow only holds ``tasks.readonly`` and
Tasks never appear in the calendar grid anyway.

The mirror is best-effort and one-directional (joidy → Google): failures
(Google down, missing re-consent, revoked token) are logged and swallowed
so task CRUD never breaks. ``google_event_id`` on the task row tracks the
remote copy; a 404 on patch means the remote event is gone and a fresh one
is created.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

import httpx
from models.calendar_task import CalendarTask, CalendarTaskPriority
from services import google_calendar_service as gcs
from services import google_service as gs
from services.google_token_service import get_valid_access_token
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PUBLISH_CALENDAR_ID = "primary"

# Fallback when the task has no parseable custom color — joidy priorities
# mapped onto the closest Google palette entries.
_PRIORITY_COLOR_ID = {
    CalendarTaskPriority.LOW: "8",  # Graphite
    CalendarTaskPriority.MEDIUM: "9",  # Blueberry
    CalendarTaskPriority.HIGH: "6",  # Tangerine
    CalendarTaskPriority.URGENT: "11",  # Tomato
}


def task_color_id(task: CalendarTask) -> str:
    """Google ``colorId`` closest to the task's joidy color/priority."""
    if task.color:
        cid = gcs.nearest_color_id(task.color)
        if cid:
            return cid
    return _PRIORITY_COLOR_ID.get(task.priority, "8")


def _event_payload(task: CalendarTask) -> dict[str, Any]:
    """All-day event resource for ``task`` (Google end date is exclusive)."""
    if task.date is None:
        raise ValueError("cannot build event payload for an undated task")
    event: dict[str, Any] = {
        "summary": task.title,
        "start": {"date": task.date.isoformat()},
        "end": {"date": (task.date + timedelta(days=1)).isoformat()},
        "colorId": task_color_id(task),
        "transparency": "transparent" if task.done else "opaque",
    }
    if task.start_time:
        when = task.start_time.strftime("%H:%M")
        if task.end_time:
            when += f" – {task.end_time.strftime('%H:%M')}"
        event["description"] = when
    return event


async def _access_token(db: Session) -> str | None:
    try:
        return await get_valid_access_token(db)
    except Exception as exc:  # token refresh failures must not break CRUD
        logger.warning("[google] Task publish: token unavailable: %s", exc)
        return None


async def _sync_async(db: Session, task: CalendarTask) -> None:
    token = await _access_token(db)
    if not token:
        return
    try:
        if task.date is None:
            if task.google_event_id:
                await gs.delete_event(token, PUBLISH_CALENDAR_ID, task.google_event_id)
                task.google_event_id = None
                db.commit()
            return

        payload = _event_payload(task)
        if task.google_event_id:
            try:
                await gs.patch_event(token, PUBLISH_CALENDAR_ID, task.google_event_id, payload)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                # Remote copy was deleted in Google — recreate below.
                task.google_event_id = None
        created = await gs.create_event(token, PUBLISH_CALENDAR_ID, payload)
        new_id = created.get("id") if isinstance(created, dict) else None
        if new_id:
            task.google_event_id = new_id
            db.commit()
    except Exception as exc:
        logger.warning("[google] Task publish failed for task %s: %s", task.id, exc)


def sync_task(db: Session, task: CalendarTask) -> None:
    """Best-effort mirror of ``task`` into Google Calendar (sync wrapper)."""
    try:
        asyncio.run(_sync_async(db, task))
    except Exception as exc:
        logger.warning("[google] Task publish crashed for task %s: %s", task.id, exc)


async def _unpublish_async(db: Session, task: CalendarTask) -> None:
    token = await _access_token(db)
    if token and task.google_event_id:
        await gs.delete_event(token, PUBLISH_CALENDAR_ID, task.google_event_id)


def unpublish_task(db: Session, task: CalendarTask) -> None:
    """Remove the mirrored Google event for ``task`` (best-effort)."""
    if not task.google_event_id:
        return
    try:
        asyncio.run(_unpublish_async(db, task))
    except Exception as exc:
        logger.warning("[google] Task unpublish failed for task %s: %s", task.id, exc)
