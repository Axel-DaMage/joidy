from fastapi.testclient import TestClient

def test_list_tags_empty(client: TestClient):
    response = client.get("/tags/")
    assert response.status_code == 200
    assert response.json() == []

def test_create_tag(client: TestClient):
    payload = {"name": "Work"}
    response = client.post("/tags/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "work"  # gets lowercased
    tag_id = data["id"]

    list_res = client.get("/tags/")
    tags = list_res.json()
    assert len(tags) == 1
    assert tags[0]["id"] == tag_id

def test_set_parent_tag(client: TestClient):
    client.post("/tags/", json={"name": "parent"})
    client.post("/tags/", json={"name": "child"})
    
    tags = client.get("/tags/").json()
    parent_id = next(t["id"] for t in tags if t["name"] == "parent")
    child_id = next(t["id"] for t in tags if t["name"] == "child")

    res = client.put(f"/tags/{child_id}/parent?parent_id={parent_id}")
    assert res.status_code == 200
    assert res.json()["parent_id"] == parent_id
