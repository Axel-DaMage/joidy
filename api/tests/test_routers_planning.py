"""Router tests for the planning assignment endpoints (#13)."""

import datetime as dt

from fastapi.testclient import TestClient
from models.calendar_task import CalendarTask, CalendarTaskSource
from models.goal import Goal
from models.planning import PlanningAssignment


def _make_goal(db_session, title="Plan Goal"):
    goal = Goal(title=title, temporality="DAILY", measurement_type="BOOLEAN")
    db_session.add(goal)
    db_session.commit()
    return goal.id


def test_get_assignments_requires_date(client: TestClient):
    response = client.get("/planning/assignments")
    assert response.status_code == 400
    assert "date" in response.json()["detail"].lower()


def test_get_assignments_invalid_date(client: TestClient):
    response = client.get("/planning/assignments?date=not-a-date")
    assert response.status_code == 400


def test_get_assignments_empty(client: TestClient):
    # Use a far-future date unlikely to have pre-existing data on shared dev DBs.
    response = client.get("/planning/assignments?date=2099-06-15")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2099-06-15"
    assert data["goal_ids"] == []


def test_set_assignments_creates_rows(client: TestClient, db_session):
    g1 = _make_goal(db_session, "G1")
    g2 = _make_goal(db_session, "G2")
    target_date = "2099-07-20"

    response = client.post(
        "/planning/assignments",
        json={
            "date": target_date,
            "goal_ids": [g1, g2],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == target_date
    assert sorted(data["goal_ids"]) == sorted([g1, g2])

    rows = (
        db_session.query(PlanningAssignment)
        .filter(PlanningAssignment.date == __import__("datetime").date(2099, 7, 20))
        .all()
    )
    assert len(rows) == 2


def test_set_assignments_replaces_existing(client: TestClient, db_session):
    g1 = _make_goal(db_session, "G1")
    g2 = _make_goal(db_session, "G2")
    g3 = _make_goal(db_session, "G3")
    target_date = "2099-08-20"

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1, g2]})
    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g3]})

    rows = (
        db_session.query(PlanningAssignment)
        .filter(PlanningAssignment.date == __import__("datetime").date(2099, 8, 20))
        .all()
    )
    assert len(rows) == 1
    assert rows[0].goal_id == g3


def test_set_assignments_invalid_date(client: TestClient):
    response = client.post(
        "/planning/assignments",
        json={
            "date": "01/15/2024",
            "goal_ids": [],
        },
    )
    assert response.status_code == 400


def test_set_then_get_assignments(client: TestClient, db_session):
    g1 = _make_goal(db_session, "G1")
    target_date = "2099-09-01"
    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1]})

    response = client.get(f"/planning/assignments?date={target_date}")
    assert response.status_code == 200
    assert response.json()["goal_ids"] == [g1]


def _tasks_on(db_session, date_obj):
    return db_session.query(CalendarTask).filter(CalendarTask.date == date_obj).all()


def test_set_assignments_mirror_creates_calendar_tasks(client: TestClient, db_session):
    g1 = _make_goal(db_session, "Mirror me")
    target_date = "2099-10-11"
    date_obj = dt.date(2099, 10, 11)

    response = client.post(
        "/planning/assignments",
        json={"date": target_date, "goal_ids": [g1], "create_calendar_task": True},
    )
    assert response.status_code == 200

    tasks = [t for t in _tasks_on(db_session, date_obj) if t.goal_id == g1]
    assert len(tasks) == 1
    assert tasks[0].title == "Mirror me"
    assert tasks[0].source == CalendarTaskSource.JOIDY

    # Re-saving the same assignments does not duplicate the task.
    client.post(
        "/planning/assignments",
        json={"date": target_date, "goal_ids": [g1], "create_calendar_task": True},
    )
    assert len([t for t in _tasks_on(db_session, date_obj) if t.goal_id == g1]) == 1

    # A goal added on a later save gets its own task; existing ones stay single.
    g2 = _make_goal(db_session, "Mirror me too")
    client.post(
        "/planning/assignments",
        json={"date": target_date, "goal_ids": [g1, g2], "create_calendar_task": True},
    )
    assert len([t for t in _tasks_on(db_session, date_obj) if t.goal_id == g1]) == 1
    assert len([t for t in _tasks_on(db_session, date_obj) if t.goal_id == g2]) == 1


def test_set_assignments_mirrors_by_default(client: TestClient, db_session):
    """Assignments mirror into calendar_tasks unless explicitly disabled."""
    g1 = _make_goal(db_session, "Default mirror")
    target_date = "2099-10-13"

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1]})

    tasks = [t for t in _tasks_on(db_session, dt.date(2099, 10, 13)) if t.goal_id == g1]
    assert len(tasks) == 1
    assert tasks[0].title == "Default mirror"


def test_set_assignments_no_mirror_when_disabled(client: TestClient, db_session):
    g1 = _make_goal(db_session, "No mirror")
    target_date = "2099-10-12"

    client.post(
        "/planning/assignments",
        json={"date": target_date, "goal_ids": [g1], "create_calendar_task": False},
    )

    tasks = [t for t in _tasks_on(db_session, dt.date(2099, 10, 12)) if t.goal_id == g1]
    assert tasks == []


def test_goal_event_ids_roundtrip(client: TestClient, db_session):
    """Event-sourced assignments keep their Google event link across saves."""
    g1 = _make_goal(db_session, "From event")
    g2 = _make_goal(db_session, "Plain")
    target_date = "2099-11-20"

    response = client.post(
        "/planning/assignments",
        json={
            "date": target_date,
            "goal_ids": [g1, g2],
            "create_calendar_task": False,
            "goal_event_ids": {str(g1): "gcal_evt_123"},
        },
    )
    assert response.status_code == 200
    assert response.json()["goal_event_ids"] == {str(g1): "gcal_evt_123"}

    got = client.get(f"/planning/assignments?date={target_date}")
    assert got.status_code == 200
    assert got.json()["goal_event_ids"] == {str(g1): "gcal_evt_123"}

    row = (
        db_session.query(PlanningAssignment)
        .filter(
            PlanningAssignment.date == dt.date(2099, 11, 20),
            PlanningAssignment.goal_id == g1,
        )
        .one()
    )
    assert row.source_event_id == "gcal_evt_123"

    # Re-saving without the map clears the link (replace semantics).
    client.post(
        "/planning/assignments",
        json={"date": target_date, "goal_ids": [g1, g2], "create_calendar_task": False},
    )
    got = client.get(f"/planning/assignments?date={target_date}")
    assert got.json()["goal_event_ids"] == {}


def test_unassign_removes_pristine_mirror_task(client: TestClient, db_session):
    """Unassigning a goal deletes the untouched mirror task it created."""
    g1 = _make_goal(db_session, "Mirror me")
    g2 = _make_goal(db_session, "Other")
    target_date = "2099-10-14"
    date_obj = dt.date(2099, 10, 14)

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1, g2]})
    assert len(_tasks_on(db_session, date_obj)) == 2

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g2]})

    remaining = _tasks_on(db_session, date_obj)
    assert len(remaining) == 1
    assert remaining[0].goal_id == g2


def test_unassign_keeps_customized_mirror_task(client: TestClient, db_session):
    """A mirror task the user edited survives unassignment as a plain task."""
    g1 = _make_goal(db_session, "Customized mirror")
    target_date = "2099-10-15"
    date_obj = dt.date(2099, 10, 15)

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1]})
    task = next(t for t in _tasks_on(db_session, date_obj) if t.goal_id == g1)
    # User gives the mirrored task a real schedule in the calendar.
    client.patch(f"/calendar/tasks/{task.id}", json={"start_time": "09:00:00", "end_time": "10:00:00"})

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": []})

    survivors = [t for t in _tasks_on(db_session, date_obj) if t.id == task.id]
    assert len(survivors) == 1
    assert survivors[0].start_time == dt.time(9, 0)
