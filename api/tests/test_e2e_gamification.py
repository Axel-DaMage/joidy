"""E2E tests for gamification endpoints via HTTP."""

from fastapi.testclient import TestClient
from models.gamification import XPEvent
from models.note import Note


def test_get_gamification_stats(client: TestClient):
    resp = client.get("/gamification/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_xp" in data


def test_get_recent_events_empty(client: TestClient):
    resp = client.get("/gamification/recent-events")
    assert resp.status_code == 200


def test_ping_event_returns_ok(client: TestClient):
    resp = client.post("/gamification/ping")
    assert resp.status_code == 200


def test_creating_note_awards_xp(client: TestClient):
    stats_before = client.get("/gamification/stats").json()
    client.post("/notes/", json={"title": "XP Note", "content": "Test", "tags": []})
    stats_after = client.get("/gamification/stats").json()
    assert stats_after["total_xp"] >= stats_before["total_xp"] + 10