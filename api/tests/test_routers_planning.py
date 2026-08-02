"""Router tests for the planning assignment endpoints (#13)."""

from fastapi.testclient import TestClient
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

    response = client.post("/planning/assignments", json={
        "date": target_date,
        "goal_ids": [g1, g2],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == target_date
    assert sorted(data["goal_ids"]) == sorted([g1, g2])

    rows = db_session.query(PlanningAssignment).filter(
        PlanningAssignment.date == __import__("datetime").date(2099, 7, 20)
    ).all()
    assert len(rows) == 2


def test_set_assignments_replaces_existing(client: TestClient, db_session):
    g1 = _make_goal(db_session, "G1")
    g2 = _make_goal(db_session, "G2")
    g3 = _make_goal(db_session, "G3")
    target_date = "2099-08-20"

    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1, g2]})
    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g3]})

    rows = db_session.query(PlanningAssignment).filter(
        PlanningAssignment.date == __import__("datetime").date(2099, 8, 20)
    ).all()
    assert len(rows) == 1
    assert rows[0].goal_id == g3


def test_set_assignments_invalid_date(client: TestClient):
    response = client.post("/planning/assignments", json={
        "date": "01/15/2024",
        "goal_ids": [],
    })
    assert response.status_code == 400


def test_set_then_get_assignments(client: TestClient, db_session):
    g1 = _make_goal(db_session, "G1")
    target_date = "2099-09-01"
    client.post("/planning/assignments", json={"date": target_date, "goal_ids": [g1]})

    response = client.get(f"/planning/assignments?date={target_date}")
    assert response.status_code == 200
    assert response.json()["goal_ids"] == [g1]
