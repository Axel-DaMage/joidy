"""Router tests for the personal streaks endpoints (#13)."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from models.personal_streaks import PersonalStreak, StreakCheckIn


def test_list_categories(client: TestClient):
    response = client.get("/personal-streaks/categories")
    assert response.status_code == 200
    cats = response.json()
    assert "general" in cats
    assert "salud" in cats
    assert "fitness" in cats


def test_list_streaks_returns_list(client: TestClient):
    response = client.get("/personal-streaks/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_streak(client: TestClient):
    payload = {
        "name": "Drink Water",
        "emoji": "💧",
        "category": "salud",
    }
    response = client.post("/personal-streaks/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Drink Water"
    assert data["emoji"] == "💧"
    assert data["category"] == "salud"
    assert data["current_streak"] == 0
    assert "id" in data


def test_create_streak_with_future_start_date_no_backfill(client: TestClient):
    future = date(2099, 1, 1)
    payload = {"name": "Future Streak", "start_date": future.isoformat()}
    response = client.post("/personal-streaks/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["start_date"] == future.isoformat()
    assert data["total_checkins"] == 0


def test_list_streaks_includes_created(client: TestClient):
    client.post("/personal-streaks/", json={"name": "Streak A"})
    client.post("/personal-streaks/", json={"name": "Streak B"})

    response = client.get("/personal-streaks/")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert "Streak A" in names
    assert "Streak B" in names


def test_update_streak(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "Original"})
    streak_id = create.json()["id"]

    response = client.put(f"/personal-streaks/{streak_id}", json={"name": "Updated", "emoji": "✅"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["emoji"] == "✅"


def test_update_streak_not_found(client: TestClient):
    response = client.put("/personal-streaks/9999", json={"name": "X"})
    assert response.status_code == 404


def test_delete_streak(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "To Delete"})
    streak_id = create.json()["id"]

    response = client.delete(f"/personal-streaks/{streak_id}")
    assert response.status_code == 204

    get_response = client.get("/personal-streaks/")
    ids = [s["id"] for s in get_response.json()]
    assert streak_id not in ids


def test_delete_streak_not_found(client: TestClient):
    response = client.delete("/personal-streaks/9999")
    assert response.status_code == 404


def test_checkin_creates_checkin(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "Checkin Streak"})
    streak_id = create.json()["id"]

    today = date.today().isoformat()
    response = client.post(f"/personal-streaks/{streak_id}/checkin", json={
        "note": "Done!",
        "mood": 4,
        "check_date": today,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["today_checked"] is True
    assert data["total_checkins"] == 1


def test_checkin_updates_existing(client: TestClient, db_session):
    create = client.post("/personal-streaks/", json={"name": "Double Checkin"})
    streak_id = create.json()["id"]

    today = date.today().isoformat()
    client.post(f"/personal-streaks/{streak_id}/checkin", json={"note": "First", "check_date": today})
    response = client.post(f"/personal-streaks/{streak_id}/checkin", json={"note": "Updated", "check_date": today})
    assert response.status_code == 200
    # Should not duplicate
    checkins = db_session.query(StreakCheckIn).filter(StreakCheckIn.streak_id == streak_id).all()
    assert len(checkins) == 1
    assert checkins[0].note == "Updated"


def test_checkin_not_found(client: TestClient):
    response = client.post("/personal-streaks/9999/checkin", json={})
    assert response.status_code == 404


def test_undo_checkin(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "Undo Streak"})
    streak_id = create.json()["id"]

    today = date.today().isoformat()
    client.post(f"/personal-streaks/{streak_id}/checkin", json={"check_date": today})
    response = client.delete(f"/personal-streaks/{streak_id}/checkin")
    assert response.status_code == 200
    assert response.json()["today_checked"] is False


def test_global_stats_shape(client: TestClient):
    response = client.get("/personal-streaks/stats")
    assert response.status_code == 200
    data = response.json()
    for key in ("total_active", "total_archived", "longest_ever", "longest_name",
                "total_checkins", "checkin_rate", "days_tracked"):
        assert key in data


def test_global_stats_with_streaks(client: TestClient):
    before = client.get("/personal-streaks/stats").json()
    client.post("/personal-streaks/", json={"name": "Active Streak Unique"})
    response = client.get("/personal-streaks/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_active"] == before["total_active"] + 1


def test_freeze_no_freezes_available(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "Freeze Streak", "freeze_count": 0})
    streak_id = create.json()["id"]

    response = client.post(f"/personal-streaks/{streak_id}/freeze")
    assert response.status_code == 400


def test_freeze_used(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "Freeze Streak", "freeze_count": 1})
    streak_id = create.json()["id"]

    response = client.post(f"/personal-streaks/{streak_id}/freeze")
    assert response.status_code == 200
    data = response.json()
    assert data["freeze_used"] == 1


def test_get_history(client: TestClient):
    create = client.post("/personal-streaks/", json={"name": "History Streak"})
    streak_id = create.json()["id"]

    today = date.today().isoformat()
    client.post(f"/personal-streaks/{streak_id}/checkin", json={"check_date": today})

    response = client.get(f"/personal-streaks/{streak_id}/history?days=30")
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 1
    assert history[0]["date"] == today


def test_get_history_not_found(client: TestClient):
    response = client.get("/personal-streaks/9999/history")
    assert response.status_code == 404
