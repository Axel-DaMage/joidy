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


def _make_note(db_session, title: str, content: str):
    from models.note import Note

    note = Note(title=title, content=content)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    return note


def test_create_goal_with_note_link(client: TestClient, db_session):
    from models.note import Note

    note = _make_note(db_session, "Proyecto X", "Contenido real de la nota")
    notes_before = db_session.query(Note).count()

    response = client.post("/goals/", json={"title": "Objetivo X", "note_id": note.id})
    assert response.status_code == 201
    data = response.json()
    assert data["note_id"] == note.id

    # Linking an existing note must NOT auto-create an extra goal note.
    assert db_session.query(Note).count() == notes_before


def test_goal_content_served_from_linked_note(client: TestClient, db_session):

    note = _make_note(db_session, "Proyecto X", "# Proyecto X\n\nContenido real")
    goal_id = client.post("/goals/", json={"title": "Objetivo X", "note_id": note.id}).json()["id"]
    db_session.commit()

    res = client.get(f"/goals/{goal_id}/content")
    assert res.status_code == 200
    body = res.json()
    assert body["content"] == "# Proyecto X\n\nContenido real"
    assert body["title"] == "Objetivo X"


def test_save_content_writes_to_linked_note(client: TestClient, db_session):
    from models.note import Note

    note = _make_note(db_session, "Proyecto X", "original")
    goal = client.post("/goals/", json={"title": "Objetivo X", "note_id": note.id}).json()

    payload = {
        "title": goal["title"],
        "content": "Nuevo contenido escrito desde el editor del objetivo",
        "temporality": goal["temporality"],
        "measurement_type": goal["measurement_type"],
        "target_value": goal["target_value"],
        "state": goal["state"],
        "fail_config": goal["fail_config"],
        "fail_emoji": goal["fail_emoji"],
        "color": goal["color"],
        "theme": goal["theme"],
        "note_id": note.id,
    }
    res = client.post(f"/goals/{goal['id']}/content", json=payload)
    assert res.status_code == 200

    linked = db_session.query(Note).filter(Note.id == note.id).first()
    assert linked is not None
    assert linked.content == "Nuevo contenido escrito desde el editor del objetivo"


def test_save_content_without_link_still_uses_goal_note(client: TestClient, db_session):
    from models.note import Note

    created = client.post("/goals/", json={"title": "Objetivo Solo"}).json()
    goal_id = created["id"]
    auto_note_id = created["note_id"]

    payload = {
        "title": created["title"],
        "content": "texto solo en la nota del objetivo",
        "temporality": created["temporality"],
        "measurement_type": created["measurement_type"],
        "target_value": created["target_value"],
        "state": created["state"],
        "fail_config": created["fail_config"],
        "fail_emoji": created["fail_emoji"],
        "color": created["color"],
        "theme": created["theme"],
        "note_id": auto_note_id,
    }
    res = client.post(f"/goals/{goal_id}/content", json=payload)
    assert res.status_code == 200

    auto_note = db_session.query(Note).filter(Note.id == auto_note_id).first()
    assert auto_note is not None
    assert "texto solo en la nota del objetivo" in auto_note.content
