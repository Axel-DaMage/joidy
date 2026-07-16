from fastapi.testclient import TestClient
from models.note import Note

def test_list_notes_empty(client: TestClient):
    response = client.get("/notes/")
    assert response.status_code == 200
    assert response.json() == []

def test_create_and_get_note(client: TestClient):
    payload = {
        "title": "Test Note",
        "content": "This is a test note #testing",
        "tags": ["testing"]
    }
    response = client.post("/notes/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Note"
    assert "testing" in data["tags"]
    note_id = data["id"]

    # Retrieve it
    get_response = client.get(f"/notes/{note_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == note_id

def test_update_note(client: TestClient):
    payload = {"title": "Original Title", "content": "Original Content", "tags": []}
    response = client.post("/notes/", json=payload)
    note_id = response.json()["id"]

    update_payload = {"title": "Updated Title"}
    update_res = client.put(f"/notes/{note_id}", json=update_payload)
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Title"
    
def test_delete_note(client: TestClient):
    payload = {"title": "To Delete", "content": "Delete me", "tags": []}
    response = client.post("/notes/", json=payload)
    note_id = response.json()["id"]

    del_res = client.delete(f"/notes/{note_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/notes/{note_id}")
    assert get_res.status_code == 404
