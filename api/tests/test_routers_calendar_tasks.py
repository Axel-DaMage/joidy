"""Router tests for the calendar tasks CRUD endpoints (#1230)."""

import datetime as dt

from fastapi.testclient import TestClient
from models.calendar_task import CalendarTask
from models.goal import Goal

FUTURE_DATE = "2099-07-20"


def _make_task(db_session, title="Test task", date=dt.date(2099, 7, 20), **kwargs):
    task = CalendarTask(title=title, date=date, **kwargs)
    db_session.add(task)
    db_session.commit()
    return task


def _make_goal(db_session, title="Linked goal", **kwargs):
    kwargs.setdefault("measurement_type", "COUNT")
    kwargs.setdefault("target_value", 3.0)
    goal = Goal(title=title, **kwargs)
    db_session.add(goal)
    db_session.commit()
    return goal


def test_list_tasks_empty(client: TestClient):
    response = client.get("/calendar/tasks?start=2099-01-01&end=2099-12-31")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task_minimal(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "Write tests", "date": FUTURE_DATE},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Write tests"
    assert data["priority"] == "MEDIUM"
    assert data["done"] is False
    assert data["source"] == "JOIDY"
    assert data["start_time"] is None


def test_create_task_full(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={
            "title": "Urgent thing",
            "date": FUTURE_DATE,
            "start_time": "10:30:00",
            "end_time": "11:30:00",
            "priority": "URGENT",
            "color": "#ff0000",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["priority"] == "URGENT"
    assert data["start_time"] == "10:30:00"
    assert data["end_time"] == "11:30:00"
    assert data["color"] == "#ff0000"


def test_create_task_rejects_empty_title(client: TestClient):
    response = client.post("/calendar/tasks", json={"title": "", "date": FUTURE_DATE})
    assert response.status_code == 422


def test_create_task_rejects_bad_priority(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "x", "date": FUTURE_DATE, "priority": "WHENEVER"},
    )
    assert response.status_code == 422


def test_create_task_rejects_end_before_start(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={
            "title": "x",
            "date": FUTURE_DATE,
            "start_time": "11:00:00",
            "end_time": "10:00:00",
        },
    )
    assert response.status_code == 400


def test_create_task_unknown_goal_404(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "x", "date": FUTURE_DATE, "goal_id": 99999999},
    )
    assert response.status_code == 404


def test_task_out_includes_goal_title(client: TestClient, db_session):
    """goal_title exposes the planning link without a second fetch."""
    goal = _make_goal(db_session, title="Ship feature")
    _make_task(db_session, title="Work on it", goal_id=goal.id)

    response = client.get("/calendar/tasks?date=2099-07-20")
    assert response.status_code == 200
    row = next(t for t in response.json() if t["title"] == "Work on it")
    assert row["goal_id"] == goal.id
    assert row["goal_title"] == "Ship feature"


def test_list_tasks_filters_by_range(client: TestClient, db_session):
    _make_task(db_session, title="In range", date=dt.date(2099, 7, 20))
    _make_task(db_session, title="Out of range", date=dt.date(2098, 1, 1))

    response = client.get("/calendar/tasks?start=2099-07-01&end=2099-07-31")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert "In range" in titles
    assert "Out of range" not in titles


def test_list_tasks_orders_by_date_then_time(client: TestClient, db_session):
    _make_task(db_session, title="Later", date=dt.date(2099, 7, 20), start_time=dt.time(14, 0))
    _make_task(db_session, title="Earlier", date=dt.date(2099, 7, 20), start_time=dt.time(9, 0))
    _make_task(db_session, title="No time", date=dt.date(2099, 7, 20))
    _make_task(db_session, title="Prev day", date=dt.date(2099, 7, 19), start_time=dt.time(20, 0))

    response = client.get("/calendar/tasks?start=2099-07-01&end=2099-07-31")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["Prev day", "Earlier", "Later", "No time"]


def test_list_tasks_filter_by_single_date(client: TestClient, db_session):
    _make_task(db_session, title="On day", date=dt.date(2099, 7, 20))
    _make_task(db_session, title="Other day", date=dt.date(2099, 7, 21))

    response = client.get("/calendar/tasks?date=2099-07-20")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["On day"]


def test_list_tasks_invalid_date_400(client: TestClient):
    assert client.get("/calendar/tasks?date=not-a-date").status_code == 400
    assert client.get("/calendar/tasks?start=20-01-2099").status_code == 400


def test_patch_task_partial(client: TestClient, db_session):
    task = _make_task(db_session, title="Original")

    response = client.patch(f"/calendar/tasks/{task.id}", json={"priority": "HIGH"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Original"
    assert data["priority"] == "HIGH"


def test_patch_task_done_sets_done_at(client: TestClient, db_session):
    task = _make_task(db_session, title="To do")

    response = client.patch(f"/calendar/tasks/{task.id}", json={"done": True})
    assert response.status_code == 200
    data = response.json()
    assert data["done"] is True
    assert data["done_at"] is not None

    response = client.patch(f"/calendar/tasks/{task.id}", json={"done": False})
    assert response.status_code == 200
    data = response.json()
    assert data["done"] is False
    assert data["done_at"] is None


def test_patch_task_rejects_bad_times(client: TestClient, db_session):
    task = _make_task(db_session, title="Times", start_time=dt.time(15, 0))

    response = client.patch(
        f"/calendar/tasks/{task.id}",
        json={"end_time": "14:00:00"},
    )
    assert response.status_code == 400


def test_patch_task_unknown_goal_404(client: TestClient, db_session):
    task = _make_task(db_session, title="With goal")

    response = client.patch(f"/calendar/tasks/{task.id}", json={"goal_id": 99999999})
    assert response.status_code == 404


def test_toggle_done(client: TestClient, db_session):
    task = _make_task(db_session, title="Toggle me")

    r1 = client.post(f"/calendar/tasks/{task.id}/done")
    assert r1.status_code == 200
    assert r1.json()["done"] is True

    r2 = client.post(f"/calendar/tasks/{task.id}/done")
    assert r2.status_code == 200
    assert r2.json()["done"] is False


def test_retoggle_done_does_not_refarm_xp(client: TestClient, db_session):
    """done → undone → done must not re-mint completion XP (audit)."""
    from models.gamification import XPEvent

    task = _make_task(db_session, title="No farming")

    for _ in range(3):
        client.post(f"/calendar/tasks/{task.id}/done")

    completed = db_session.query(XPEvent).filter(XPEvent.event_type == "calendar_task_completed_no_time").all()
    assert len(completed) == 1
    planned = db_session.query(XPEvent).filter(XPEvent.event_type == "day_fully_planned").all()
    assert len(planned) == 1


def test_delete_task(client: TestClient, db_session):
    task = _make_task(db_session, title="Delete me")

    response = client.delete(f"/calendar/tasks/{task.id}")
    assert response.status_code == 204
    assert client.get(f"/calendar/tasks?date={FUTURE_DATE}").json() == []


def test_404_on_missing_task(client: TestClient):
    assert client.patch("/calendar/tasks/99999999", json={"title": "x"}).status_code == 404
    assert client.delete("/calendar/tasks/99999999").status_code == 404
    assert client.post("/calendar/tasks/99999999/done").status_code == 404


# ── Unscheduled queue (#1234) ──────────────────────────────────────────────


def test_create_task_without_date(client: TestClient):
    response = client.post("/calendar/tasks", json={"title": "No day yet"})
    assert response.status_code == 201
    assert response.json()["date"] is None


def test_list_tasks_unscheduled(client: TestClient, db_session):
    _make_task(db_session, title="Queued", date=None)
    _make_task(db_session, title="Scheduled")

    response = client.get("/calendar/tasks?unscheduled=true")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["Queued"]


def test_list_tasks_date_filters_exclude_unscheduled(client: TestClient, db_session):
    _make_task(db_session, title="Queued", date=None)
    _make_task(db_session, title="Scheduled")

    response = client.get("/calendar/tasks?date=2099-07-20")
    assert [t["title"] for t in response.json()] == ["Scheduled"]

    response = client.get("/calendar/tasks?start=2099-01-01&end=2099-12-31")
    assert [t["title"] for t in response.json()] == ["Scheduled"]


def test_patch_task_schedule_and_unschedule(client: TestClient, db_session):
    task = _make_task(db_session, title="Floating", date=None)

    response = client.patch(f"/calendar/tasks/{task.id}", json={"date": FUTURE_DATE})
    assert response.status_code == 200
    assert response.json()["date"] == FUTURE_DATE

    response = client.patch(f"/calendar/tasks/{task.id}", json={"date": None})
    assert response.status_code == 200
    assert response.json()["date"] is None


# ── Execution queue (#1234) ────────────────────────────────────────────────


def test_execution_queue_orders_by_priority_then_time(client: TestClient, db_session):
    day = dt.date(2099, 7, 21)
    _make_task(db_session, title="Low early", date=day, priority="LOW", start_time=dt.time(8, 0))
    _make_task(db_session, title="Medium", date=day, priority="MEDIUM")
    _make_task(db_session, title="Urgent", date=day, priority="URGENT")
    _make_task(db_session, title="High timed", date=day, priority="HIGH", start_time=dt.time(9, 0))
    _make_task(db_session, title="Done urgent", date=day, priority="URGENT", done=True)
    _make_task(db_session, title="Other day", date=dt.date(2099, 7, 22), priority="URGENT")

    response = client.get("/calendar/tasks/execution-queue?date=2099-07-21")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["Urgent", "High timed", "Medium", "Low early"]


def test_execution_queue_timeless_last(client: TestClient, db_session):
    day = dt.date(2099, 7, 23)
    _make_task(db_session, title="No time", date=day, priority="HIGH")
    _make_task(db_session, title="Timed", date=day, priority="HIGH", start_time=dt.time(18, 0))

    response = client.get("/calendar/tasks/execution-queue?date=2099-07-23")
    assert [t["title"] for t in response.json()] == ["Timed", "No time"]


def test_execution_queue_invalid_date_400(client: TestClient):
    assert client.get("/calendar/tasks/execution-queue?date=nope").status_code == 400


# ── Goal progress on task completion (#1234) ───────────────────────────────


def test_toggle_done_advances_count_goal(client: TestClient, db_session):
    goal = _make_goal(db_session, title="3 things", target_value=3.0)
    task = _make_task(db_session, title="Step", goal_id=goal.id)

    response = client.post(f"/calendar/tasks/{task.id}/done")
    assert response.status_code == 200
    db_session.refresh(goal)
    assert goal.current_value == 1.0

    # Un-completing removes the contribution — no double counting.
    client.post(f"/calendar/tasks/{task.id}/done")
    db_session.refresh(goal)
    assert goal.current_value == 0.0

    # Re-completing counts exactly once more.
    client.post(f"/calendar/tasks/{task.id}/done")
    db_session.refresh(goal)
    assert goal.current_value == 1.0


def test_patch_done_advances_goal_once(client: TestClient, db_session):
    goal = _make_goal(db_session, title="Patch goal")
    task = _make_task(db_session, title="Step", goal_id=goal.id)

    client.patch(f"/calendar/tasks/{task.id}", json={"done": True})
    db_session.refresh(goal)
    assert goal.current_value == 1.0

    # Re-sending done=true is not a new edge — no extra progress.
    client.patch(f"/calendar/tasks/{task.id}", json={"done": True})
    db_session.refresh(goal)
    assert goal.current_value == 1.0


def test_tag_count_goal_not_touched(client: TestClient, db_session):
    from models.note import Tag

    tag = Tag(name="tag-goal-probe")
    db_session.add(tag)
    db_session.commit()
    goal = _make_goal(db_session, title="Tag goal", tag_id=tag.id)
    task = _make_task(db_session, title="Step", goal_id=goal.id)

    client.post(f"/calendar/tasks/{task.id}/done")
    db_session.refresh(goal)
    assert goal.current_value == 0.0


def test_done_goalless_or_missing_goal_is_safe(client: TestClient, db_session):
    task = _make_task(db_session, title="Free task")
    response = client.post(f"/calendar/tasks/{task.id}/done")
    assert response.status_code == 200
    assert response.json()["done"] is True


# ── Recurrence + reminders (#1238) ─────────────────────────────────────────


def _tasks_on(db_session, day: dt.date, title: str):
    return db_session.query(CalendarTask).filter(CalendarTask.date == day, CalendarTask.title == title).all()


def test_task_out_carries_recurrence_and_reminder(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "Check mail", "date": FUTURE_DATE, "recurrence": "DAILY", "reminder_minutes": 15},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["recurrence"] == "DAILY"
    assert data["reminder_minutes"] == 15


def test_create_task_defaults_no_recurrence_no_reminder(client: TestClient):
    response = client.post("/calendar/tasks", json={"title": "One-off", "date": FUTURE_DATE})
    assert response.status_code == 201
    data = response.json()
    assert data["recurrence"] == "NONE"
    assert data["reminder_minutes"] is None


def test_done_spawns_daily_occurrence(client: TestClient, db_session):
    task = _make_task(
        db_session,
        title="Standup",
        date=dt.date(2099, 8, 1),
        recurrence="DAILY",
        start_time=dt.time(9, 0),
        end_time=dt.time(9, 15),
        priority="HIGH",
        color="#123456",
        reminder_minutes=10,
        google_event_id="g-evt-1",
    )
    response = client.post(f"/calendar/tasks/{task.id}/done")
    assert response.status_code == 200

    spawned = _tasks_on(db_session, dt.date(2099, 8, 2), "Standup")
    assert len(spawned) == 1
    occ = spawned[0]
    assert occ.id != task.id
    assert occ.done is False
    assert occ.recurrence.value == "DAILY"
    assert occ.start_time == dt.time(9, 0)
    assert occ.end_time == dt.time(9, 15)
    assert occ.priority.value == "HIGH"
    assert occ.color == "#123456"
    assert occ.reminder_minutes == 10
    # Fresh occurrence: it must not claim the parent's Google mirror.
    assert occ.google_event_id is None


def test_done_spawns_weekly_occurrence(client: TestClient, db_session):
    task = _make_task(db_session, title="Weekly review", date=dt.date(2099, 7, 30), recurrence="WEEKLY")
    client.post(f"/calendar/tasks/{task.id}/done")
    spawned = _tasks_on(db_session, dt.date(2099, 8, 6), "Weekly review")
    assert len(spawned) == 1


def test_done_spawns_monthly_same_day(client: TestClient, db_session):
    task = _make_task(db_session, title="Pay rent", date=dt.date(2099, 1, 15), recurrence="MONTHLY")
    client.post(f"/calendar/tasks/{task.id}/done")
    spawned = _tasks_on(db_session, dt.date(2099, 2, 15), "Pay rent")
    assert len(spawned) == 1


def test_done_spawns_monthly_clamps_month_end(client: TestClient, db_session):
    # 2099 is not a leap year: Jan 31 → Feb 28 (clamped, no dateutil needed).
    task = _make_task(db_session, title="Month-end", date=dt.date(2099, 1, 31), recurrence="MONTHLY")
    client.post(f"/calendar/tasks/{task.id}/done")
    assert len(_tasks_on(db_session, dt.date(2099, 2, 28), "Month-end")) == 1
    assert len(_tasks_on(db_session, dt.date(2099, 3, 3), "Month-end")) == 0


def test_retoggle_done_does_not_duplicate_occurrence(client: TestClient, db_session):
    task = _make_task(db_session, title="No dupes", date=dt.date(2099, 8, 1), recurrence="DAILY")
    for _ in range(3):
        client.post(f"/calendar/tasks/{task.id}/done")
    assert len(_tasks_on(db_session, dt.date(2099, 8, 2), "No dupes")) == 1


def test_done_without_recurrence_spawns_nothing(client: TestClient, db_session):
    task = _make_task(db_session, title="One-off", date=dt.date(2099, 8, 1))
    client.post(f"/calendar/tasks/{task.id}/done")
    assert len(_tasks_on(db_session, dt.date(2099, 8, 2), "One-off")) == 0


def test_goal_linked_recurring_task_does_not_spawn(client: TestClient, db_session):
    goal = _make_goal(db_session, title="Recurring goal")
    task = _make_task(db_session, title="Goal step", date=dt.date(2099, 8, 1), recurrence="DAILY", goal_id=goal.id)
    client.post(f"/calendar/tasks/{task.id}/done")
    assert len(_tasks_on(db_session, dt.date(2099, 8, 2), "Goal step")) == 0


def test_unscheduled_recurring_task_does_not_spawn(client: TestClient, db_session):
    task = _make_task(db_session, title="Floating daily", date=None, recurrence="DAILY")
    response = client.post(f"/calendar/tasks/{task.id}/done")
    assert response.status_code == 200
    remaining = db_session.query(CalendarTask).filter(CalendarTask.title == "Floating daily").all()
    assert len(remaining) == 1


def test_patch_done_via_update_spawns_occurrence(client: TestClient, db_session):
    task = _make_task(db_session, title="Patch spawn", date=dt.date(2099, 8, 1), recurrence="DAILY")
    client.patch(f"/calendar/tasks/{task.id}", json={"done": True})
    assert len(_tasks_on(db_session, dt.date(2099, 8, 2), "Patch spawn")) == 1


def test_patch_task_updates_recurrence(client: TestClient, db_session):
    task = _make_task(db_session, title="Make weekly")
    response = client.patch(f"/calendar/tasks/{task.id}", json={"recurrence": "WEEKLY"})
    assert response.status_code == 200
    assert response.json()["recurrence"] == "WEEKLY"


def test_reminder_minutes_bounds(client: TestClient, db_session):
    task = _make_task(db_session, title="Remind me")
    assert (
        client.post("/calendar/tasks", json={"title": "x", "date": FUTURE_DATE, "reminder_minutes": -5}).status_code
        == 422
    )
    assert (
        client.post("/calendar/tasks", json={"title": "x", "date": FUTURE_DATE, "reminder_minutes": 1441}).status_code
        == 422
    )
    response = client.patch(f"/calendar/tasks/{task.id}", json={"reminder_minutes": 30})
    assert response.status_code == 200
    assert response.json()["reminder_minutes"] == 30
    # Explicit null clears the reminder.
    response = client.patch(f"/calendar/tasks/{task.id}", json={"reminder_minutes": None})
    assert response.status_code == 200
    assert response.json()["reminder_minutes"] is None


def test_create_task_rejects_bad_recurrence(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "x", "date": FUTURE_DATE, "recurrence": "YEARLY"},
    )
    assert response.status_code == 422


# ── Event-editor fields + duplicate (#1658) ──────────────────────────────────


def test_create_task_with_event_fields(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={
            "title": "Team sync",
            "date": FUTURE_DATE,
            "description": "Weekly catch-up",
            "location": "Room 42",
            "attendees": "a@example.com, b@example.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Weekly catch-up"
    assert data["location"] == "Room 42"
    assert data["attendees"] == "a@example.com, b@example.com"
    assert data["note_id"] is None


def test_patch_task_event_fields(client: TestClient, db_session):
    task = _make_task(db_session, title="Old")
    response = client.patch(
        f"/calendar/tasks/{task.id}",
        json={"description": "new desc", "location": "HQ", "attendees": "c@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "new desc"
    assert data["location"] == "HQ"
    assert data["attendees"] == "c@example.com"
    # Explicit null clears them again.
    response = client.patch(
        f"/calendar/tasks/{task.id}",
        json={"description": None, "location": None, "attendees": None},
    )
    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["location"] is None


def test_patch_task_note_id_validates_note(client: TestClient, db_session):
    from models.note import Note

    task = _make_task(db_session, title="With note")
    assert client.patch(f"/calendar/tasks/{task.id}", json={"note_id": 999}).status_code == 404
    note = Note(title="Vault note")
    db_session.add(note)
    db_session.commit()
    response = client.patch(f"/calendar/tasks/{task.id}", json={"note_id": note.id})
    assert response.status_code == 200
    assert response.json()["note_id"] == note.id


def test_duplicate_task_copies_fields(client: TestClient, db_session):
    task = _make_task(
        db_session,
        title="Source",
        description="desc",
        location="loc",
        attendees="a@x.com",
        color="#abc",
        recurrence="WEEKLY",
        reminder_minutes=15,
        done=True,
        google_event_id="g-123",
    )
    response = client.post(f"/calendar/tasks/{task.id}/duplicate")
    assert response.status_code == 201
    data = response.json()
    assert data["id"] != task.id
    assert data["title"] == "Source"
    assert data["description"] == "desc"
    assert data["location"] == "loc"
    assert data["attendees"] == "a@x.com"
    assert data["color"] == "#abc"
    assert data["recurrence"] == "WEEKLY"
    assert data["reminder_minutes"] == 15
    # Clone always starts open and detached from Google.
    assert data["done"] is False
    assert data["google_event_id"] is None
    assert data["source"] == "JOIDY"


def test_duplicate_task_with_overrides(client: TestClient, db_session):
    task = _make_task(db_session, title="Move me", date=dt.date(2099, 7, 20))
    response = client.post(
        f"/calendar/tasks/{task.id}/duplicate",
        json={"date": "2099-07-25", "title": "Moved"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Moved"
    assert data["date"] == "2099-07-25"


def test_duplicate_task_404(client: TestClient):
    assert client.post("/calendar/tasks/999/duplicate").status_code == 404


# ── Google Calendar auto-mirror (#task-google-sync) ─────────────────────


def test_create_task_with_date_syncs_google(client: TestClient, monkeypatch):
    calls = []
    monkeypatch.setattr("services.task_google_sync.sync_task", lambda db, t: calls.append(t.id))
    response = client.post("/calendar/tasks", json={"title": "Publish me", "date": FUTURE_DATE})
    assert response.status_code == 201
    assert len(calls) == 1


def test_create_unscheduled_task_skips_google(client: TestClient, monkeypatch):
    calls = []
    monkeypatch.setattr("services.task_google_sync.sync_task", lambda db, t: calls.append(t.id))
    response = client.post("/calendar/tasks", json={"title": "Inbox"})
    assert response.status_code == 201
    assert calls == []


def test_reschedule_syncs_google(client: TestClient, db_session, monkeypatch):
    task = _make_task(db_session, title="Move me")
    calls = []
    monkeypatch.setattr("services.task_google_sync.sync_task", lambda db, t: calls.append(t.id))
    response = client.patch(f"/calendar/tasks/{task.id}", json={"date": "2099-07-21"})
    assert response.status_code == 200
    assert calls == [task.id]


def test_unrelated_update_skips_google(client: TestClient, db_session, monkeypatch):
    task = _make_task(db_session, title="Reminder only")
    calls = []
    monkeypatch.setattr("services.task_google_sync.sync_task", lambda db, t: calls.append(t.id))
    response = client.patch(f"/calendar/tasks/{task.id}", json={"reminder_minutes": 30})
    assert response.status_code == 200
    assert calls == []


def test_done_toggle_syncs_google(client: TestClient, db_session, monkeypatch):
    task = _make_task(db_session, title="Toggle me")
    calls = []
    monkeypatch.setattr("services.task_google_sync.sync_task", lambda db, t: calls.append(t.id))
    response = client.post(f"/calendar/tasks/{task.id}/done")
    assert response.status_code == 200
    assert calls == [task.id]


def test_delete_task_unpublishes_google(client: TestClient, db_session, monkeypatch):
    task = _make_task(db_session, title="Delete me")
    calls = []
    monkeypatch.setattr("services.task_google_sync.unpublish_task", lambda db, t: calls.append(t.id))
    response = client.delete(f"/calendar/tasks/{task.id}")
    assert response.status_code == 204
    assert calls == [task.id]
