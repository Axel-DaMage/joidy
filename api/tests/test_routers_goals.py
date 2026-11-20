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


def _goal_ids(client: TestClient) -> list[int]:
    return [g["id"] for g in client.get("/goals/").json()]


def test_create_goal_defaults_priority_to_zero(client: TestClient):
    data = client.post("/goals/", json={"title": "Sin prioridad"}).json()
    assert data["priority"] == 0


def test_create_goal_rejects_out_of_range_priority(client: TestClient):
    res = client.post("/goals/", json={"title": "X", "priority": 100})
    assert res.status_code == 422


def test_list_goals_orders_by_priority_desc(client: TestClient):
    low = client.post("/goals/", json={"title": "Baja", "priority": 1}).json()
    neutral = client.post("/goals/", json={"title": "Neutra"}).json()
    high = client.post("/goals/", json={"title": "Alta", "priority": 5}).json()

    ids = _goal_ids(client)
    assert ids.index(high["id"]) < ids.index(low["id"]) < ids.index(neutral["id"])


def test_completed_goals_stay_last_regardless_of_priority(client: TestClient):
    done = client.post("/goals/", json={"title": "Hecho", "priority": 5}).json()
    client.post(f"/goals/{done['id']}/complete")
    active = client.post("/goals/", json={"title": "Activo"}).json()

    ids = _goal_ids(client)
    assert ids.index(active["id"]) < ids.index(done["id"])


def test_update_goal_priority(client: TestClient):
    goal = client.post("/goals/", json={"title": "Editable"}).json()

    res = client.put(f"/goals/{goal['id']}", json={"priority": 3})
    assert res.status_code == 200
    assert res.json()["priority"] == 3

    res = client.put(f"/goals/{goal['id']}", json={"priority": -1})
    assert res.status_code == 422


def test_save_content_preserves_priority(client: TestClient):
    goal = client.post("/goals/", json={"title": "Con prioridad", "priority": 4}).json()

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": goal["title"], "content": "contenido nuevo"},
    )
    assert res.status_code == 200
    assert res.json()["priority"] == 4


def test_sort_goals_updates_priorities_in_bulk(client: TestClient):
    a = client.post("/goals/", json={"title": "A"}).json()
    b = client.post("/goals/", json={"title": "B"}).json()

    res = client.patch(
        "/goals/sort",
        json={"items": [{"id": a["id"], "priority": 5}, {"id": b["id"], "priority": 2}]},
    )
    assert res.status_code == 200
    assert res.json()["updated"] == 2

    priorities = {g["id"]: g["priority"] for g in client.get("/goals/").json()}
    assert priorities[a["id"]] == 5
    assert priorities[b["id"]] == 2


def test_sort_goals_missing_id_returns_404(client: TestClient):
    goal = client.post("/goals/", json={"title": "Existente"}).json()

    res = client.patch(
        "/goals/sort",
        json={"items": [{"id": goal["id"], "priority": 1}, {"id": 999999, "priority": 2}]},
    )
    assert res.status_code == 404

    priorities = {g["id"]: g["priority"] for g in client.get("/goals/").json()}
    assert priorities[goal["id"]] == 0


def test_sort_goals_rejects_out_of_range_priority(client: TestClient):
    goal = client.post("/goals/", json={"title": "X"}).json()

    res = client.patch("/goals/sort", json={"items": [{"id": goal["id"], "priority": 100}]})
    assert res.status_code == 422


def test_sort_goals_rejects_duplicate_ids(client: TestClient):
    goal = client.post("/goals/", json={"title": "X"}).json()

    res = client.patch(
        "/goals/sort",
        json={"items": [{"id": goal["id"], "priority": 1}, {"id": goal["id"], "priority": 2}]},
    )
    assert res.status_code == 422


# ── #1319 — GoalContent sanitization, FK existence, state mass-assignment ──


def test_save_content_sanitizes_title_xss(client: TestClient):
    goal = client.post("/goals/", json={"title": "Normal goal"}).json()

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": "<img src=x onerror=alert(1)>", "content": "body"},
    )
    assert res.status_code == 200
    title = res.json()["title"]
    assert "onerror" not in title
    assert "alert" not in title
    assert client.get(f"/goals/{goal['id']}").json()["title"] == title


def test_save_content_rejects_theme_newline(client: TestClient):
    goal = client.post("/goals/", json={"title": "Frontmatter target"}).json()

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": "Frontmatter target", "content": "body", "theme": "x\nstate: COMPLETED"},
    )
    assert res.status_code == 422
    assert client.get(f"/goals/{goal['id']}").json()["theme"] == "solid"


def test_save_content_theme_injection_leaves_vault_file_untouched(client: TestClient, tmp_path, monkeypatch):
    """With a vault configured, a rejected theme must not corrupt the goal
    .md file — frontmatter bytes stay identical (#1319)."""
    from config import settings

    monkeypatch.setattr(settings, "obsidian_vault_path", str(tmp_path))

    goal = client.post("/goals/", json={"title": "Vault goal"}).json()
    obj_dir = tmp_path / "Objetivos"
    files = list(obj_dir.glob(f"{goal['id']}_*.md"))
    assert len(files) == 1
    before = files[0].read_text(encoding="utf-8")

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": "Vault goal", "content": "new body", "theme": "x\nstate: COMPLETED"},
    )
    assert res.status_code == 422
    assert files[0].read_text(encoding="utf-8") == before


def test_save_content_rejects_title_newline(client: TestClient):
    goal = client.post("/goals/", json={"title": "T"}).json()

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": "ok\ninjected body line", "content": "c"},
    )
    assert res.status_code == 422


def test_save_content_ignores_state_field(client: TestClient):
    """The editor echoes state back on every save; it must never be
    mass-assigned — a COMPLETED payload cannot fabricate completion (#1319)."""
    goal = client.post("/goals/", json={"title": "Echo"}).json()

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": "Echo", "content": "c", "state": "COMPLETED"},
    )
    assert res.status_code == 200
    assert res.json()["state"] == "ACTIVE"
    assert res.json()["is_completed"] is False


def test_update_goal_rejects_terminal_states(client: TestClient):
    goal = client.post("/goals/", json={"title": "No cheat"}).json()

    for state in ("COMPLETED", "FAILED"):
        res = client.put(f"/goals/{goal['id']}", json={"state": state})
        assert res.status_code == 422, state

    body = client.get(f"/goals/{goal['id']}").json()
    assert body["state"] == "ACTIVE"
    assert body["is_completed"] is False


def test_create_goal_rejects_terminal_states(client: TestClient):
    for state in ("COMPLETED", "FAILED"):
        res = client.post("/goals/", json={"title": "T", "state": state})
        assert res.status_code == 422, state


def test_update_goal_still_allows_nonterminal_states(client: TestClient):
    """Pause/cancel/reactivate/un-complete via PUT keep working (#1319)."""
    goal = client.post("/goals/", json={"title": "Lifecycle"}).json()

    for state in ("PAUSED", "ACTIVE", "CANCELLED", "INBOX", "ACTIVE"):
        res = client.put(f"/goals/{goal['id']}", json={"state": state})
        assert res.status_code == 200, state
        assert res.json()["state"] == state


def test_update_goal_ignores_current_value(client: TestClient):
    goal = client.post("/goals/", json={"title": "Progress"}).json()

    res = client.put(f"/goals/{goal['id']}", json={"current_value": 999})
    assert res.status_code == 200
    assert res.json()["current_value"] == 0


def test_update_goal_ignores_is_completed(client: TestClient):
    goal = client.post("/goals/", json={"title": "Flags"}).json()

    res = client.put(f"/goals/{goal['id']}", json={"is_completed": True})
    assert res.status_code == 200
    assert res.json()["is_completed"] is False


def test_create_goal_rejects_nonexistent_note(client: TestClient):
    res = client.post("/goals/", json={"title": "Bad link", "note_id": 999999})
    assert res.status_code == 404


def test_update_goal_rejects_nonexistent_note(client: TestClient):
    goal = client.post("/goals/", json={"title": "T"}).json()

    res = client.put(f"/goals/{goal['id']}", json={"note_id": 999999})
    assert res.status_code == 404
    assert client.get(f"/goals/{goal['id']}").json()["note_id"] == goal["note_id"]


def test_save_content_rejects_nonexistent_note(client: TestClient):
    goal = client.post("/goals/", json={"title": "T"}).json()

    res = client.post(
        f"/goals/{goal['id']}/content",
        json={"title": "T", "content": "c", "note_id": 999999},
    )
    assert res.status_code == 404
    # Existing link untouched.
    assert client.get(f"/goals/{goal['id']}").json()["note_id"] == goal["note_id"]


def test_update_goal_rejects_nonexistent_tag(client: TestClient):
    goal = client.post("/goals/", json={"title": "T"}).json()

    res = client.put(f"/goals/{goal['id']}", json={"tag_id": 999999})
    assert res.status_code == 404
