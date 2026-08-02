"""Router tests for the stats endpoints (#13)."""

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from models.gamification import UserStats, XPEvent
from models.goal import Goal
from models.note import Note, Tag as TagModel
from models.skill import Skill


def test_system_stats_shape(client: TestClient):
    response = client.get("/stats/system")
    assert response.status_code == 200
    data = response.json()
    for key in ("notes", "tags", "goals", "skills", "total_xp", "current_streak", "xp_events_week"):
        assert key in data
        assert isinstance(data[key], int)


def test_system_stats_with_data(client: TestClient, db_session):
    before = client.get("/stats/system").json()

    tag = TagModel(name=f"t1-stats-{uuid.uuid4().hex[:8]}")
    db_session.add(tag)
    db_session.flush()
    db_session.add_all([
        Note(title="Note A stats", content="a"),
        Note(title="Note B stats", content="b"),
        Goal(title="G1 stats", temporality="DAILY", measurement_type="BOOLEAN"),
        Skill(tag_id=tag.id, note_count=5),
        XPEvent(event_type="note_created", xp=10),
        XPEvent(event_type="note_created", xp=10),
    ])
    # Update or create UserStats (id=1 may already exist on shared dev DB).
    stats = db_session.query(UserStats).filter(UserStats.id == 1).first()
    if stats is None:
        stats = UserStats(id=1)
        db_session.add(stats)
    stats.total_xp = 250
    stats.current_streak = 5
    db_session.commit()

    response = client.get("/stats/system")
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == before["notes"] + 2
    assert data["tags"] == before["tags"] + 1
    assert data["goals"] == before["goals"] + 1
    assert data["skills"] == before["skills"] + 1
    assert data["total_xp"] == 250
    assert data["current_streak"] == 5
    assert data["xp_events_week"] == before["xp_events_week"] + 2


def test_activity_stats_default_days(client: TestClient):
    response = client.get("/stats/activity")
    assert response.status_code == 200
    data = response.json()
    assert "days" in data
    assert len(data["days"]) == 30
    today_entry = data["days"][0]
    assert "date" in today_entry
    assert "notes_created" in today_entry
    assert "xp_events" in today_entry


def test_activity_stats_custom_days(client: TestClient):
    response = client.get("/stats/activity?days=7")
    assert response.status_code == 200
    assert len(response.json()["days"]) == 7


def test_activity_stats_days_clamped_to_366(client: TestClient):
    response = client.get("/stats/activity?days=500")
    assert response.status_code == 200
    assert len(response.json()["days"]) == 366


def test_activity_stats_invalid_days(client: TestClient):
    response = client.get("/stats/activity?days=0")
    assert response.status_code == 400


def test_activity_stats_reflects_notes(client: TestClient, db_session):
    db_session.add(Note(title="Today", content="x"))
    db_session.commit()

    response = client.get("/stats/activity?days=3")
    assert response.status_code == 200
    today_entry = response.json()["days"][0]
    assert today_entry["notes_created"] >= 1
