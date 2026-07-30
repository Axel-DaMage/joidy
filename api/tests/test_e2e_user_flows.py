"""End-to-end user flows across notes, goals, tags and streaks."""


def _check(resp, expected: int, label: str):
    if resp.status_code != expected:
        print(f"[{label}] Unexpected status {resp.status_code}: {resp.text}")
    assert resp.status_code == expected, f"{label}: expected {expected}, got {resp.status_code}"


def test_full_note_goal_and_streak_flow(client):
    """Create a note, a goal, a tag and verify a streak check-in."""

    # 1. Create a note
    resp = client.post("/notes/", json={
        "title": "E2E note",
        "content": "Test content",
        "tags": ["e2e"],
    })
    _check(resp, 201, "create note")
    note = resp.json()
    note_id = note["id"]
    assert note["title"] == "E2E note"

    # 2. Fetch notes and confirm it appears
    resp = client.get("/notes/?limit=100")
    _check(resp, 200, "list notes")
    notes = resp.json()
    assert any(n["id"] == note_id for n in notes)

    # 3. Create a goal
    resp = client.post("/goals/", json={
        "title": "E2E goal",
        "description": "Complete the e2e flow",
        "temporality": "WEEKLY",
        "measurement_type": "COUNT",
        "target_value": 1,
        "state": "ACTIVE",
    })
    _check(resp, 201, "create goal")
    goal = resp.json()
    goal_id = goal["id"]
    assert goal["title"] == "E2E goal"

    # 4. Mark the goal as completed
    resp = client.post(f"/goals/{goal_id}/complete")
    _check(resp, 200, "complete goal")
    completed = resp.json()
    assert completed["goal"]["is_completed"] is True

    # 5. Tag graph should contain the new tag and note
    resp = client.get("/tags/graph")
    _check(resp, 200, "tag graph")
    graph = resp.json()
    assert any(n.get("type") == "tag" for n in graph["nodes"])
    assert any(n.get("type") == "note" for n in graph["nodes"])

    # 6. Create a personal streak and check in
    resp = client.post("/personal-streaks/", json={
        "name": "E2E streak",
        "description": "Daily test streak",
        "frequency_days": 1,
    })
    _check(resp, 201, "create streak")
    streak = resp.json()
    streak_id = streak["id"]

    resp = client.post(f"/personal-streaks/{streak_id}/checkin", json={
        "note": "first check-in",
        "mood": 5,
    })
    _check(resp, 200, "checkin streak")
    checkin = resp.json()
    assert checkin["id"] == streak_id
    assert checkin["current_streak"] >= 1
