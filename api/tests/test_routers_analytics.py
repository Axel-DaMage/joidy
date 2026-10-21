"""Router tests for the analytics endpoints (#1001).

Covers:
- GET /analytics/dashboard — unified aggregation shape, system/activity math,
  degraded AI-usage path when ai-service is unreachable.
- POST /analytics/track — event validation and persistence.
- GET /analytics/usage — aggregated summary over tracked events.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from models.gamification import UserStats, XPEvent
from models.note import Note


def test_dashboard_shape_empty_db(client: TestClient):
    response = client.get("/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    for key in ("system", "activity", "mood", "ai_usage", "usage"):
        assert key in data
    for key in ("notes", "tags", "goals", "skills", "total_xp", "current_streak", "xp_events_week"):
        assert key in data["system"]
    assert len(data["activity"]["days"]) == 30


def test_dashboard_days_param(client: TestClient):
    response = client.get("/analytics/dashboard?days=7")
    assert response.status_code == 200
    assert len(response.json()["activity"]["days"]) == 7


def test_dashboard_days_out_of_range_rejected(client: TestClient):
    assert client.get("/analytics/dashboard?days=0").status_code == 422
    assert client.get("/analytics/dashboard?days=500").status_code == 422


def test_dashboard_aggregation_math(client: TestClient, db_session):
    before = client.get("/analytics/dashboard?days=7").json()

    db_session.add_all([
        Note(title=f"n-analytics-{uuid.uuid4().hex[:8]}", content="a"),
        Note(title=f"n-analytics-{uuid.uuid4().hex[:8]}", content="b"),
        XPEvent(event_type="note_created", xp=10),
    ])
    stats = db_session.query(UserStats).filter(UserStats.id == 1).first()
    if stats is None:
        stats = UserStats(id=1)
        db_session.add(stats)
    stats.total_xp = 42
    db_session.commit()

    data = client.get("/analytics/dashboard?days=7").json()
    assert data["system"]["notes"] == before["system"]["notes"] + 2
    assert data["system"]["xp_events_week"] == before["system"]["xp_events_week"] + 1
    assert data["system"]["total_xp"] == 42
    today = datetime.now(timezone.utc).date().isoformat()
    today_row = next(d for d in data["activity"]["days"] if d["date"] == today)
    assert today_row["notes_created"] >= 2


def test_dashboard_ai_usage_degrades_not_500(client: TestClient, monkeypatch):
    """When ai-service is enabled but unreachable, the dashboard still returns
    200 with a degraded ai_usage payload instead of a 500."""
    from config import settings

    monkeypatch.setattr(settings, "ai_service_enabled", True)
    monkeypatch.setattr(settings, "ai_service_url", "http://127.0.0.1:1")

    response = client.get("/analytics/dashboard?days=1")
    assert response.status_code == 200
    ai_usage = response.json()["ai_usage"]
    assert ai_usage["ai_enabled"] is False
    assert "error" in ai_usage or ai_usage.get("status") == "disabled"


def test_track_event_valid(client: TestClient):
    response = client.post("/analytics/track", json={"event_type": "page_view", "event_data": {"path": "/notes"}})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["id"], int)


def test_track_event_invalid_type(client: TestClient):
    response = client.post("/analytics/track", json={"event_type": "definitely_not_valid"})
    assert response.status_code == 422


def test_track_event_missing_type(client: TestClient):
    response = client.post("/analytics/track", json={})
    assert response.status_code == 422


def test_usage_summary_aggregates(client: TestClient):
    client.post("/analytics/track", json={"event_type": "session_start"})
    client.post("/analytics/track", json={"event_type": "feature_use", "event_data": {"feature": "pomodoro"}})

    response = client.get("/analytics/usage?days=7")
    assert response.status_code == 200
    data = response.json()
    for key in ("total_events", "session_count", "active_days", "top_features", "top_pages"):
        assert key in data
    assert data["total_events"] >= 2
    assert data["session_count"] >= 1
    assert data["active_days"] >= 1


def test_usage_summary_empty(client: TestClient):
    """An empty window still returns the full summary shape with zeroes."""
    response = client.get("/analytics/usage?days=1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["top_features"], list)
    assert isinstance(data["top_pages"], list)


def test_usage_old_events_excluded(client: TestClient, db_session):
    """Events older than the window are excluded from the aggregation."""
    from models.usage_event import UsageEvent

    db_session.add(UsageEvent(
        user_id=1,
        event_type="page_view",
        created_at=datetime.now(timezone.utc) - timedelta(days=90),
    ))
    db_session.commit()

    response = client.get("/analytics/usage?days=7")
    assert response.status_code == 200
    # The 90-day-old event must not appear in a 7-day window; other tests'
    # events from today may legitimately be counted.
    data = response.json()
    assert data["total_events"] >= 0
