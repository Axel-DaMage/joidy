"""E2E tests for note CRUD lifecycle via HTTP."""

from fastapi.testclient import TestClient


def test_create_note_minimal(client: TestClient):
    payload = {"title": "Minimal Note", "content": "Hello", "tags": []}
    resp = client.post("/notes/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Minimal Note"
    assert "id" in data


def test_create_note_with_tags(client: TestClient):
    payload = {"title": "Tagged Note", "content": "Has tags", "tags": ["e2e", "test"]}
    resp = client.post("/notes/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "test" in data["tags"]
    assert "e2e" in data["tags"]


def test_list_notes_includes_new(client: TestClient):
    client.post("/notes/", json={"title": "List Test", "content": "X", "tags": []})
    resp = client.get("/notes/")
    assert resp.status_code == 200
    notes = resp.json()
    assert any(n["title"] == "List Test" for n in notes)


def test_get_note_by_id(client: TestClient):
    create = client.post("/notes/", json={"title": "Get Me", "content": "Find", "tags": []}).json()
    resp = client.get(f"/notes/{create['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Me"


def test_get_nonexistent_note_returns_404(client: TestClient):
    resp = client.get("/notes/999999")
    assert resp.status_code == 404


def test_update_note_title(client: TestClient):
    create = client.post("/notes/", json={"title": "Old", "content": "X", "tags": []}).json()
    resp = client.put(f"/notes/{create['id']}", json={"title": "New"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"


def test_update_note_content_and_tags(client: TestClient):
    create = client.post("/notes/", json={"title": "Upd", "content": "Old", "tags": ["a"]}).json()
    resp = client.put(f"/notes/{create['id']}", json={"content": "New", "tags": ["b"]})
    assert resp.status_code == 200
    data = resp.json()
    assert "b" in data["tags"]
    assert "a" not in data["tags"]


def test_delete_note(client: TestClient):
    create = client.post("/notes/", json={"title": "Del", "content": "X", "tags": []}).json()
    resp = client.delete(f"/notes/{create['id']}")
    assert resp.status_code == 204
    get_resp = client.get(f"/notes/{create['id']}")
    assert get_resp.status_code == 404


def test_note_create_invalid_title_returns_422(client: TestClient):
    resp = client.post("/notes/", json={"content": "No title", "tags": []})
    assert resp.status_code == 422


def test_note_rebuild_derived(client: TestClient):
    resp = client.post("/notes/rebuild-derived")
    assert resp.status_code == 202