"""Tests for POST /gamification/pomodoro — XP for completed focus sessions.

Anti-farm contract (#1133): sessions under MIN_POMODORO_XP_MINUTES never award
XP, and replaying the same pomodoro_id is idempotent. Multiple pomodoros per
day are legitimate, so unlike daily_activity there is no daily cap.

Like test_routers_tags.py, assertions filter XP events by a per-test unique
pomodoro_id: committed rows can leak between tests on the local SQLite
fallback (the wipe only runs against Postgres test DBs).
"""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from models.gamification import XPEvent


def _pomodoro_events(db_session, pomodoro_id: str):
    events = db_session.query(XPEvent).filter(XPEvent.event_type == "pomodoro_completed").all()
    return [e for e in events if json.loads(e.metadata_json or "{}").get("pomodoro_id") == pomodoro_id]


def test_completed_pomodoro_awards_15_xp(client: TestClient, db_session):
    pomodoro_id = f"pom-{uuid4().hex[:8]}"
    stats_before = client.get("/gamification/stats").json()

    res = client.post(
        "/gamification/pomodoro",
        json={"duration_minutes": 25, "pomodoro_id": pomodoro_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "awarded"
    assert data["xp_awarded"] >= 15
    assert data["total_xp"] > stats_before["total_xp"]

    events = _pomodoro_events(db_session, pomodoro_id)
    assert len(events) == 1
    assert events[0].xp == 15
    meta = json.loads(events[0].metadata_json)
    assert meta["pomodoro_id"] == pomodoro_id
    assert meta["duration_minutes"] == 25


def test_short_session_does_not_award(client: TestClient, db_session):
    pomodoro_id = f"pom-{uuid4().hex[:8]}"

    res = client.post(
        "/gamification/pomodoro",
        json={"duration_minutes": 10, "pomodoro_id": pomodoro_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "too_short"
    assert data["xp_awarded"] == 0
    assert _pomodoro_events(db_session, pomodoro_id) == []


def test_invalid_duration_returns_422(client: TestClient):
    assert client.post("/gamification/pomodoro", json={"duration_minutes": 0}).status_code == 422
    assert client.post("/gamification/pomodoro", json={"duration_minutes": -5}).status_code == 422
    assert client.post("/gamification/pomodoro", json={}).status_code == 422


def test_duplicate_pomodoro_id_is_idempotent(client: TestClient, db_session):
    pomodoro_id = f"pom-{uuid4().hex[:8]}"
    payload = {"duration_minutes": 25, "pomodoro_id": pomodoro_id}

    first = client.post("/gamification/pomodoro", json=payload)
    assert first.json()["status"] == "awarded"
    assert first.json()["xp_awarded"] >= 15
    stats_mid = client.get("/gamification/stats").json()

    second = client.post("/gamification/pomodoro", json=payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["xp_awarded"] == 0
    assert second.json()["total_xp"] == stats_mid["total_xp"]

    assert len(_pomodoro_events(db_session, pomodoro_id)) == 1


def test_multiple_pomodoros_per_day_all_award(client: TestClient, db_session):
    pomodoro_ids = [f"pom-{uuid4().hex[:8]}" for _ in range(3)]

    for pomodoro_id in pomodoro_ids:
        res = client.post(
            "/gamification/pomodoro",
            json={"duration_minutes": 25, "pomodoro_id": pomodoro_id},
        )
        assert res.json()["status"] == "awarded"

    for pomodoro_id in pomodoro_ids:
        assert len(_pomodoro_events(db_session, pomodoro_id)) == 1


def test_pomodoro_id_optional(client: TestClient, db_session):
    duration = 37  # uncommon value to filter this test's event out of leaks

    res = client.post("/gamification/pomodoro", json={"duration_minutes": duration})
    assert res.status_code == 200
    assert res.json()["status"] == "awarded"

    events = [
        e
        for e in db_session.query(XPEvent).filter(XPEvent.event_type == "pomodoro_completed").all()
        if json.loads(e.metadata_json or "{}").get("duration_minutes") == duration
        and json.loads(e.metadata_json or "{}").get("pomodoro_id") is None
    ]
    assert len(events) == 1
