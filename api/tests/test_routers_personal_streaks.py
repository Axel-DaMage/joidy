"""Router tests for the personal streaks endpoints (#13)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from models.personal_streaks import StreakCheckIn


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
    # Future start dates within the planning horizon (~1y) are allowed — the
    # UI lets users schedule a streak — but must not trigger backfill (#1321).
    future = date.today() + timedelta(days=30)
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
    response = client.post(
        f"/personal-streaks/{streak_id}/checkin",
        json={
            "note": "Done!",
            "mood": 4,
            "check_date": today,
        },
    )
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
    for key in (
        "total_active",
        "total_archived",
        "longest_ever",
        "longest_name",
        "total_checkins",
        "checkin_rate",
        "days_tracked",
    ):
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


# ── Input validation (#1321) ────────────────────────────────────────────────────


def _create_streak(client: TestClient, name: str = "Validation Streak") -> int:
    resp = client.post("/personal-streaks/", json={"name": name})
    assert resp.status_code == 201
    return int(resp.json()["id"])


def test_create_streak_rejects_absurd_past_start_date(client: TestClient):
    """start_date=0001-01-01 used to trigger a ~740k-row backfill (#1321)."""
    resp = client.post("/personal-streaks/", json={"name": "Ancient", "start_date": "0001-01-01"})
    assert resp.status_code == 422


def test_create_streak_rejects_far_future_start_date(client: TestClient):
    resp = client.post("/personal-streaks/", json={"name": "Far Future", "start_date": "2099-01-01"})
    assert resp.status_code == 422


def test_create_streak_accepts_reasonable_past_start_date(client: TestClient):
    start = date.today() - timedelta(days=10)
    resp = client.post("/personal-streaks/", json={"name": "Recent", "start_date": start.isoformat()})
    assert resp.status_code == 201


def test_create_streak_rejects_out_of_range_fields(client: TestClient):
    for payload in (
        {"name": "NegOffset", "offset": -1},
        {"name": "HugeOffset", "offset": 10**9},
        {"name": "NegFreeze", "freeze_count": -1},
        {"name": "HugeFreeze", "freeze_count": 10**6},
        {"name": "BadFreq", "frequency": "fortnightly-ish"},
        {"name": "ZeroFreqDays", "frequency_days": 0},
        {"name": "HugeFreqDays", "frequency_days": 99999},
        {"name": "   "},  # whitespace-only name
        {"name": "LongCat", "category": "x" * 51},
        {"name": "LongNote2", "description": "x" * 2001},
    ):
        resp = client.post("/personal-streaks/", json=payload)
        assert resp.status_code == 422, f"expected 422 for {payload}, got {resp.status_code}"


def test_create_streak_normalizes_frequency_case(client: TestClient):
    resp = client.post("/personal-streaks/", json={"name": "CaseFreq", "frequency": "DAILY"})
    assert resp.status_code == 201
    assert resp.json()["frequency"] == "daily"


def test_update_streak_rejects_server_computed_fields(client: TestClient):
    """best_streak / total_checkins / freeze_used are server-computed and must
    not be mass-assignable through the update schema (#1321)."""
    streak_id = _create_streak(client)
    for field in ("best_streak", "total_checkins", "freeze_used", "current_streak"):
        resp = client.put(f"/personal-streaks/{streak_id}", json={field: 9999})
        assert resp.status_code == 422, f"{field} should be rejected"
    # Stored server-computed values must be untouched.
    streak = next(s for s in client.get("/personal-streaks/").json() if s["id"] == streak_id)
    assert streak["best_streak"] == 0
    assert streak["freeze_used"] == 0
    assert streak["total_checkins"] == 0


def test_update_streak_rejects_invalid_field_values(client: TestClient):
    streak_id = _create_streak(client)
    for payload in (
        {"freeze_count": -1},
        {"freeze_count": 10**6},
        {"frequency_days": 0},
        {"frequency": "bogus"},
    ):
        resp = client.put(f"/personal-streaks/{streak_id}", json=payload)
        assert resp.status_code == 422, f"expected 422 for {payload}"


def test_checkin_rejects_future_check_date(client: TestClient):
    streak_id = _create_streak(client)
    resp = client.post(f"/personal-streaks/{streak_id}/checkin", json={"check_date": "2030-01-01"})
    assert resp.status_code == 422


def test_checkin_rejects_absurd_past_check_date(client: TestClient):
    streak_id = _create_streak(client)
    resp = client.post(f"/personal-streaks/{streak_id}/checkin", json={"check_date": "0001-01-01"})
    assert resp.status_code == 422


def test_checkin_rejects_out_of_range_mood(client: TestClient):
    streak_id = _create_streak(client)
    today = date.today().isoformat()
    for mood in (0, 6, -1, 99):
        resp = client.post(
            f"/personal-streaks/{streak_id}/checkin",
            json={"check_date": today, "mood": mood},
        )
        assert resp.status_code == 422, f"mood={mood} should be rejected"


def test_checkin_accepts_boundary_moods(client: TestClient):
    streak_id = _create_streak(client)
    today = date.today().isoformat()
    for mood in (1, 5):
        resp = client.post(
            f"/personal-streaks/{streak_id}/checkin",
            json={"check_date": today, "mood": mood},
        )
        assert resp.status_code == 200, f"mood={mood} should be accepted"


def test_checkin_rejects_oversized_note_and_extra_fields(client: TestClient):
    streak_id = _create_streak(client)
    resp = client.post(
        f"/personal-streaks/{streak_id}/checkin",
        json={"check_date": date.today().isoformat(), "note": "x" * 501},
    )
    assert resp.status_code == 422
    resp = client.post(
        f"/personal-streaks/{streak_id}/checkin",
        json={"check_date": date.today().isoformat(), "best_streak": 999},
    )
    assert resp.status_code == 422


def test_checkin_valid_payload_still_works(client: TestClient):
    streak_id = _create_streak(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    resp = client.post(
        f"/personal-streaks/{streak_id}/checkin",
        json={"check_date": yesterday, "note": "backfill note", "mood": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["total_checkins"] == 1


def test_backfill_capped_for_old_start_date(client: TestClient):
    """A start_date near the 5y validation bound must never generate more than
    MAX_BACKFILL_DAYS check-ins in a single create call (#1321)."""
    start = date.today() - timedelta(days=1500)
    resp = client.post(
        "/personal-streaks/",
        json={"name": "Long History", "start_date": start.isoformat()},
    )
    assert resp.status_code == 201
    data = resp.json()
    # 400-day service cap respected; backfill still produced recent history.
    assert 0 < data["total_checkins"] <= 400


def test_mood_rejects_out_of_range_score_and_oversized_note(client: TestClient):
    for payload in (
        {"score": 0},
        {"score": 6},
        {"score": 3, "note": "x" * 501},
    ):
        resp = client.post("/mood/", json=payload)
        assert resp.status_code == 422, f"expected 422 for {payload}"


def test_mood_valid_payload_still_works(client: TestClient):
    resp = client.post("/mood/", json={"score": 4, "note": "Solid day"})
    assert resp.status_code == 200
    assert resp.json()["score"] == 4
