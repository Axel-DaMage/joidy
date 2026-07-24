"""E2E tests for goal CRUD lifecycle via HTTP."""

from fastapi.testclient import TestClient


def test_create_goal(client: TestClient):
    payload = {"title": "E2E Goal", "description": "Test", "temporality": "DAILY", "target_value": 1}
    resp = client.post("/goals/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "E2E Goal"


def test_list_goals(client: TestClient):
    client.post("/goals/", json={"title": "List Goal", "temporality": "DAILY", "target_value": 1})
    resp = client.get("/goals/")
    assert resp.status_code == 200
    goals = resp.json()
    assert any(g["title"] == "List Goal" for g in goals)


def test_get_goal_by_id(client: TestClient):
    create = client.post("/goals/", json={"title": "Get Goal", "temporality": "DAILY", "target_value": 1}).json()
    resp = client.get(f"/goals/{create['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Goal"


def test_get_nonexistent_goal_returns_404(client: TestClient):
    resp = client.get("/goals/999999")
    assert resp.status_code == 404


def test_complete_goal(client: TestClient):
    create = client.post("/goals/", json={"title": "Complete Me", "temporality": "DAILY", "target_value": 1}).json()
    resp = client.post(f"/goals/{create['id']}/complete")
    assert resp.status_code == 200


def test_delete_goal(client: TestClient):
    create = client.post("/goals/", json={"title": "Delete Me", "temporality": "DAILY", "target_value": 1}).json()
    resp = client.delete(f"/goals/{create['id']}")
    assert resp.status_code == 204