from fastapi.testclient import TestClient

def test_list_goals_empty(client: TestClient):
    response = client.get("/goals/")
    assert response.status_code == 200
    assert response.json() == []

def test_create_goal(client: TestClient):
    payload = {
        "title": "Read a book",
        "temporality": "DAILY",
        "measurement_type": "BOOLEAN",
    }
    response = client.post("/goals/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Read a book"
    goal_id = data["id"]

    get_res = client.get(f"/goals/{goal_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Read a book"

def test_complete_goal(client: TestClient):
    payload = {
        "title": "Drink water",
        "temporality": "DAILY",
        "measurement_type": "BOOLEAN",
    }
    create_res = client.post("/goals/", json=payload)
    goal_id = create_res.json()["id"]

    comp_res = client.post(f"/goals/{goal_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json()["goal"]["is_completed"] is True
