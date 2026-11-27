"""Unit tests for the joidy → Google Calendar task mirror (#task-google-sync)."""

import asyncio
import datetime as dt

import httpx
import pytest
from models.calendar_task import CalendarTask, CalendarTaskPriority
from services import task_google_sync as tgs


def _make_task(db_session, **kwargs):
    kwargs.setdefault("title", "Mirror me")
    kwargs.setdefault("date", dt.date(2099, 7, 20))
    task = CalendarTask(**kwargs)
    db_session.add(task)
    db_session.commit()
    return task


def _fake_token(monkeypatch, token="tok"):
    async def _token(db):
        return token

    monkeypatch.setattr(tgs, "get_valid_access_token", _token)


def test_payload_is_all_day_with_exclusive_end(db_session):
    task = _make_task(db_session)
    payload = tgs._event_payload(task)
    assert payload["start"] == {"date": "2099-07-20"}
    assert payload["end"] == {"date": "2099-07-21"}
    assert payload["summary"] == "Mirror me"
    assert payload["transparency"] == "opaque"
    assert "timeZone" not in str(payload["start"])


def test_payload_done_task_is_transparent(db_session):
    task = _make_task(db_session, done=True)
    assert tgs._event_payload(task)["transparency"] == "transparent"


def test_payload_includes_time_description(db_session):
    task = _make_task(db_session, start_time=dt.time(9, 30), end_time=dt.time(11, 0))
    assert tgs._event_payload(task)["description"] == "09:30 – 11:00"


def test_color_id_prefers_custom_color(db_session):
    task = _make_task(db_session, color="#d9534f", priority=CalendarTaskPriority.LOW)
    # #d9534f is closest to Google Tomato ("11"), not the LOW fallback.
    assert tgs.task_color_id(task) == "11"


def test_color_id_falls_back_to_priority(db_session):
    assert tgs.task_color_id(_make_task(db_session, priority=CalendarTaskPriority.URGENT)) == "11"
    assert tgs.task_color_id(_make_task(db_session, priority=CalendarTaskPriority.LOW)) == "8"
    assert tgs.task_color_id(_make_task(db_session, color="var(--accent)")) == "9"


def test_nearest_color_id_rejects_garbage():
    assert tgs.gcs.nearest_color_id("not-a-color") is None
    assert tgs.gcs.nearest_color_id("#fff") == "8"  # #ffffff → Graphite


def test_sync_creates_event_and_stores_id(db_session, monkeypatch):
    _fake_token(monkeypatch)
    seen = {}

    async def _create(token, calendar_id, payload):
        seen["calendar_id"] = calendar_id
        seen["payload"] = payload
        return {"id": "gev-1"}

    monkeypatch.setattr(tgs.gs, "create_event", _create)
    task = _make_task(db_session)
    asyncio.run(tgs._sync_async(db_session, task))
    db_session.refresh(task)
    assert task.google_event_id == "gev-1"
    assert seen["calendar_id"] == "primary"
    assert seen["payload"]["start"] == {"date": "2099-07-20"}


def test_sync_patches_existing_event(db_session, monkeypatch):
    _fake_token(monkeypatch)
    calls = {"patch": 0, "create": 0}

    async def _patch(token, calendar_id, event_id, payload):
        calls["patch"] += 1
        calls["event_id"] = event_id
        return {"id": event_id}

    async def _create(token, calendar_id, payload):
        calls["create"] += 1
        return {"id": "should-not-happen"}

    monkeypatch.setattr(tgs.gs, "patch_event", _patch)
    monkeypatch.setattr(tgs.gs, "create_event", _create)
    task = _make_task(db_session, google_event_id="gev-old")
    asyncio.run(tgs._sync_async(db_session, task))
    assert calls["patch"] == 1 and calls["create"] == 0
    assert calls["event_id"] == "gev-old"


def test_sync_recreates_on_remote_404(db_session, monkeypatch):
    _fake_token(monkeypatch)

    async def _patch(token, calendar_id, event_id, payload):
        raise httpx.HTTPStatusError(
            "gone",
            request=httpx.Request("PATCH", "https://example.com"),
            response=httpx.Response(404),
        )

    async def _create(token, calendar_id, payload):
        return {"id": "gev-new"}

    monkeypatch.setattr(tgs.gs, "patch_event", _patch)
    monkeypatch.setattr(tgs.gs, "create_event", _create)
    task = _make_task(db_session, google_event_id="gev-deleted")
    asyncio.run(tgs._sync_async(db_session, task))
    db_session.refresh(task)
    assert task.google_event_id == "gev-new"


def test_sync_unschedules_deletes_remote(db_session, monkeypatch):
    _fake_token(monkeypatch)
    deleted = []

    async def _delete(token, calendar_id, event_id):
        deleted.append(event_id)

    monkeypatch.setattr(tgs.gs, "delete_event", _delete)
    task = _make_task(db_session, date=None, google_event_id="gev-x")
    asyncio.run(tgs._sync_async(db_session, task))
    db_session.refresh(task)
    assert deleted == ["gev-x"]
    assert task.google_event_id is None


def test_sync_without_token_is_noop(db_session, monkeypatch):
    _fake_token(monkeypatch, token=None)
    called = []

    async def _create(token, calendar_id, payload):
        called.append(1)
        return {"id": "x"}

    monkeypatch.setattr(tgs.gs, "create_event", _create)
    task = _make_task(db_session)
    asyncio.run(tgs._sync_async(db_session, task))
    assert called == []


def test_sync_swallows_google_errors(db_session, monkeypatch):
    _fake_token(monkeypatch)

    async def _boom(token, calendar_id, payload):
        raise RuntimeError("google down")

    monkeypatch.setattr(tgs.gs, "create_event", _boom)
    task = _make_task(db_session)
    # Must not raise — CRUD stays intact.
    asyncio.run(tgs._sync_async(db_session, task))


@pytest.mark.parametrize(
    "priority,color,expected",
    [
        (CalendarTaskPriority.LOW, None, "8"),
        (CalendarTaskPriority.MEDIUM, None, "9"),
        (CalendarTaskPriority.HIGH, None, "6"),
        (CalendarTaskPriority.URGENT, None, "11"),
        (CalendarTaskPriority.MEDIUM, "#ff0000", "11"),  # pure red → Tomato
    ],
)
def test_task_color_id_mapping(priority, color, expected):
    task = CalendarTask(title="t", date=dt.date(2099, 1, 1), priority=priority, color=color)
    assert tgs.task_color_id(task) == expected
