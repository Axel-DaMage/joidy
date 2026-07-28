"""E2E tests for tag CRUD via HTTP."""

from fastapi.testclient import TestClient


def test_create_tag(client: TestClient):
    resp = client.post("/tags/", json={"name": "e2e-tag"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "e2e-tag"
    assert "id" in data


def test_create_duplicate_tag_returns_409(client: TestClient):
    client.post("/tags/", json={"name": "dup-tag"})
    resp = client.post("/tags/", json={"name": "dup-tag"})
    assert resp.status_code == 409


def test_list_tags(client: TestClient):
    client.post("/tags/", json={"name": "list-tag"})
    resp = client.get("/tags/")
    assert resp.status_code == 200
    tags = resp.json()
    assert any(t["name"] == "list-tag" for t in tags)


def test_set_tag_parent(client: TestClient):
    parent = client.post("/tags/", json={"name": "parent-tag"}).json()
    child = client.post("/tags/", json={"name": "child-tag"}).json()
    resp = client.put(f"/tags/{child['id']}/parent?parent_id={parent['id']}")
    assert resp.status_code == 200


def test_cannot_set_self_as_parent(client: TestClient):
    tag = client.post("/tags/", json={"name": "self-tag"}).json()
    resp = client.put(f"/tags/{tag['id']}/parent?parent_id={tag['id']}")
    assert resp.status_code == 400


def test_tag_graph_endpoint(client: TestClient):
    resp = client.get("/tags/graph")
    assert resp.status_code == 200