"""Extra coverage for ``routers/goals.py`` (#1401).

Existing goal tests cover list/create basics; this file pins the missed
surface: create/update validators, FK existence checks, parent-hierarchy
rules, sort, execution queue, content read/write (incl. the linked-note
mirror), complete/fail/delete lifecycle, and pending-removal resolution.
Vault writes are redirected to ``tmp_path`` where exercised.
"""

from datetime import datetime

from models.goal import Goal, GoalContext, GoalFailConfig, GoalState, GoalTemporality
from models.note import Note, Tag


def _goal(db, **kwargs) -> Goal:
    goal = Goal(title=kwargs.pop("title", "goal"), **kwargs)
    db.add(goal)
    db.flush()
    return goal


def _note(db, **kwargs) -> Note:
    note = Note(title=kwargs.pop("title", "n"), content=kwargs.pop("content", "body"), source="joidy", **kwargs)
    db.add(note)
    db.flush()
    return note


def _tag(db, name="goal-tag") -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.flush()
    return tag


def _goal_payload(**over):
    payload = {"title": "extra goal"}
    payload.update(over)
    return payload


# ─── create ───────────────────────────────────────────────────────────────────


def test_create_goal_full_payload(client):
    resp = client.post(
        "/goals/",
        json=_goal_payload(
            description="desc",
            temporality="WEEKLY",
            context="MORNING",
            measurement_type="COUNT",
            target_value=3.0,
            state="PAUSED",
            fail_config="ROLLOVER",
            fail_emoji="🔥",
            color="#ff0000",
            theme="gradient",
            priority=7,
            max_assignment_days=2,
        ),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["temporality"] == "WEEKLY"
    assert data["priority"] == 7
    assert data["note_id"] is not None  # auto-created backing note


def test_create_goal_validation_errors(client):
    assert client.post("/goals/", json=_goal_payload(target_value=0)).status_code == 422
    assert client.post("/goals/", json=_goal_payload(state="COMPLETED")).status_code == 422
    assert client.post("/goals/", json=_goal_payload(state="FAILED")).status_code == 422
    assert client.post("/goals/", json=_goal_payload(priority=100)).status_code == 422
    assert client.post("/goals/", json=_goal_payload(priority=-1)).status_code == 422
    assert client.post("/goals/", json=_goal_payload(title="bad\ntitle")).status_code == 422


def test_create_goal_with_existing_links(client, db_session):
    note = _note(db_session)
    tag = _tag(db_session)
    parent = _goal(db_session, title="parent")
    db_session.commit()

    resp = client.post(
        "/goals/",
        json=_goal_payload(note_id=note.id, tag_id=tag.id, parent_id=parent.id),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["note_id"] == note.id
    assert data["tag_id"] == tag.id
    assert data["parent_id"] == parent.id

    # Bogus FK targets → 404 (note/tag) or 400 (missing parent)
    assert client.post("/goals/", json=_goal_payload(note_id=999999)).status_code == 404
    assert client.post("/goals/", json=_goal_payload(tag_id=999999)).status_code == 404
    assert client.post("/goals/", json=_goal_payload(parent_id=999999)).status_code == 400


# ─── update ───────────────────────────────────────────────────────────────────


def test_update_goal_fields_and_404(client, db_session):
    goal = _goal(db_session, title="orig")
    db_session.commit()

    resp = client.put(
        f"/goals/{goal.id}",
        json={"title": "renamed", "priority": 50, "context": "NIGHT"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "renamed"
    assert resp.json()["priority"] == 50

    assert client.put("/goals/999999", json={"title": "x"}).status_code == 404


def test_update_goal_fk_checks(client, db_session):
    parent = _goal(db_session, title="p")
    child = _goal(db_session, title="c", parent_id=parent.id)
    db_session.commit()

    # GoalUpdate has no parent_id field — a stray value is ignored by
    # Pydantic rather than reaching validate_goal_parent.
    resp = client.put(f"/goals/{parent.id}", json={"parent_id": child.id})
    assert resp.status_code == 200
    assert resp.json()["parent_id"] is None

    assert client.put(f"/goals/{child.id}", json={"note_id": 999999}).status_code == 404
    assert client.put(f"/goals/{child.id}", json={"tag_id": 999999}).status_code == 404


def test_update_goal_content_mirrors_linked_note(client, db_session, monkeypatch, tmp_path):
    """PUT with ``content`` writes the goal file AND mirrors into the linked note."""
    monkeypatch.setattr("services.joidy_vault_writer.get_vault_path", lambda: tmp_path)
    note = _note(db_session, content="old body")
    goal = _goal(db_session, title="linked", note_id=note.id)
    db_session.commit()

    resp = client.put(
        f"/goals/{goal.id}",
        json={"title": "linked", "content": "# Objetivo: nuevo cuerpo"},
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    assert db_session.get(Note, note.id).content == "# Objetivo: nuevo cuerpo"
    # The vault goal file was written under tmp_path/Objetivos/
    obj_dir = tmp_path / "Objetivos"
    assert obj_dir.is_dir()
    assert list(obj_dir.glob(f"{goal.id}_*.md"))


# ─── sort / execution queue ───────────────────────────────────────────────────


def test_sort_goals(client, db_session):
    g1 = _goal(db_session, title="s1")
    g2 = _goal(db_session, title="s2")
    db_session.commit()

    resp = client.patch("/goals/sort", json={"items": [{"id": g1.id, "priority": 9}, {"id": g2.id, "priority": 3}]})
    assert resp.status_code == 200
    assert resp.json() == {"updated": 2}

    # Duplicate ids → 422; unknown id → 404; out-of-range priority → 422
    assert (
        client.patch(
            "/goals/sort", json={"items": [{"id": g1.id, "priority": 1}, {"id": g1.id, "priority": 2}]}
        ).status_code
        == 422
    )
    assert client.patch("/goals/sort", json={"items": [{"id": 999999, "priority": 1}]}).status_code == 404
    assert client.patch("/goals/sort", json={"items": [{"id": g1.id, "priority": 100}]}).status_code == 422


def test_execution_queue_contexts(client, db_session):
    _goal(db_session, title="any-task", context=GoalContext.ANY, priority=5)
    _goal(db_session, title="morning-task", context=GoalContext.MORNING, priority=9)
    _goal(db_session, title="night-task", context=GoalContext.NIGHT, priority=1)
    _goal(db_session, title="done-task", context=GoalContext.ANY, state=GoalState.COMPLETED, is_completed=True)
    db_session.commit()

    for ctx, expected_titles in (
        ("morning", {"any-task", "morning-task"}),
        ("night", {"any-task", "night-task"}),
        ("auto", None),  # resolved by current UTC hour — just assert shape
    ):
        resp = client.get("/goals/execution-queue", params={"context": ctx})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["context"] in ("MORNING", "NIGHT")
        titles = {i["title"] for i in data["items"]}
        assert "done-task" not in titles
        if expected_titles is not None:
            assert titles == expected_titles
        # Priority DESC ordering
        priorities = [i["priority"] for i in data["items"]]
        assert priorities == sorted(priorities, reverse=True)


# ─── get / content ────────────────────────────────────────────────────────────


def test_get_goal_and_content_404s(client):
    assert client.get("/goals/999999").status_code == 404
    assert client.get("/goals/999999/content").status_code == 404


def test_get_goal_content_linked_note_and_file(client, db_session, monkeypatch, tmp_path):
    # Linked note → note content is the source of truth
    note = _note(db_session, content="note body wins")
    linked = _goal(db_session, title="linked", note_id=note.id)
    # Unlinked goal → falls back to the vault goal file when present
    plain = _goal(db_session, title="plain")
    monkeypatch.setattr("services.joidy_vault_writer.get_vault_path", lambda: tmp_path)
    obj_dir = tmp_path / "Objetivos"
    obj_dir.mkdir(parents=True)
    (obj_dir / f"{plain.id}_plain.md").write_text(
        "---\ntitle: Plain File\n---\n# Plain File\n\nfile body here\n", encoding="utf-8"
    )
    db_session.commit()

    resp = client.get(f"/goals/{linked.id}/content")
    assert resp.status_code == 200
    assert resp.json()["content"] == "note body wins"

    resp = client.get(f"/goals/{plain.id}/content")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Plain File"
    assert data["content"] == "file body here"


def test_get_goal_content_default_payload(client, db_session):
    goal = _goal(db_session, title="no-file", description="the desc")
    db_session.commit()
    resp = client.get(f"/goals/{goal.id}/content")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "no-file"
    assert data["content"] == "the desc"
    # Goal model default temporality is DAILY.
    assert data["temporality"] == "DAILY"


# ─── save content ─────────────────────────────────────────────────────────────


def _content_payload(goal, **over):
    payload = {
        "title": goal.title,
        "content": "editor body",
        "temporality": "DAILY",
        "context": "ANY",
        "measurement_type": "COUNT",
        "target_value": 2.0,
        "state": "ACTIVE",
        "fail_config": "STATIC",
        "fail_emoji": "❌",
        "color": "#123456",
        "theme": "solid",
        "note_id": None,
        "tag_id": None,
        "parent_id": None,
        "max_assignment_days": None,
        "description": "",
    }
    payload.update(over)
    return payload


def test_save_goal_content(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr("services.joidy_vault_writer.get_vault_path", lambda: tmp_path)
    note = _note(db_session)
    tag = _tag(db_session)
    goal = _goal(db_session, title="editable")
    db_session.commit()

    resp = client.post(
        f"/goals/{goal.id}/content",
        json=_content_payload(goal, note_id=note.id, tag_id=tag.id, description="d2"),
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    refreshed = db_session.get(Goal, goal.id)
    assert refreshed.note_id == note.id
    assert refreshed.tag_id == tag.id
    # The endpoint maps the editor body onto goal.description.
    assert refreshed.description == "editor body"
    # Content was mirrored into the linked note.
    assert db_session.get(Note, note.id).content == "editor body"
    # Goal file written under the fake vault.
    assert list((tmp_path / "Objetivos").glob(f"{goal.id}_*.md"))


def test_save_goal_content_404_and_fk_checks(client, db_session):
    goal = _goal(db_session, title="g")
    db_session.commit()
    assert client.post("/goals/999999/content", json=_content_payload(goal)).status_code == 404
    assert client.post(f"/goals/{goal.id}/content", json=_content_payload(goal, note_id=999999)).status_code == 404
    assert client.post(f"/goals/{goal.id}/content", json=_content_payload(goal, tag_id=999999)).status_code == 404


def test_save_goal_content_ignores_state_field(client, db_session):
    """#1319 — a COMPLETED echo in the payload must not fabricate completion."""
    goal = _goal(db_session, title="stateguard")
    db_session.commit()
    resp = client.post(
        f"/goals/{goal.id}/content",
        json=_content_payload(goal, state="COMPLETED"),
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "ACTIVE"
    assert resp.json()["is_completed"] is False


# ─── complete / fail / delete / resolve-removal ───────────────────────────────


def test_complete_and_refail_idempotent(client, db_session):
    goal = _goal(db_session, title="finish-me", target_value=1.0, current_value=1.0)
    db_session.commit()

    resp = client.post(f"/goals/{goal.id}/complete")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["goal"]["state"] == "COMPLETED"
    assert data["goal"]["is_completed"] is True
    assert data.get("already_completed") in (None, False)

    # Replay → idempotent no-op, no second XP mint
    resp = client.post(f"/goals/{goal.id}/complete")
    assert resp.status_code == 200
    assert resp.json()["already_completed"] is True

    assert client.post("/goals/999999/complete").status_code == 404


def test_complete_failed_snowball_adjusts_child(client, db_session, monkeypatch, tmp_path):
    """Completing a late FAILED snowball goal shrinks the accumulated child."""
    monkeypatch.setattr("services.joidy_vault_writer.get_vault_path", lambda: tmp_path)
    parent = _goal(
        db_session,
        title="snow-parent",
        temporality=GoalTemporality.DAILY,
        fail_config=GoalFailConfig.SNOWBALL,
        target_value=10.0,
        current_value=4.0,
        state=GoalState.FAILED,
        created_at=datetime(2026, 1, 1),
    )
    child = _goal(
        db_session,
        title="snow-parent",
        temporality=GoalTemporality.DAILY,
        fail_config=GoalFailConfig.SNOWBALL,
        target_value=16.0,
        current_value=0.0,
        state=GoalState.ACTIVE,
        created_at=datetime(2026, 1, 2),
    )
    db_session.commit()

    resp = client.post(f"/goals/{parent.id}/complete")
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    refreshed_child = db_session.get(Goal, child.id)
    # shortfall = 10 - 4 = 6 → child target = max(10, 16 - 6) = 10
    assert refreshed_child.target_value == 10.0


def test_fail_and_delete_goal(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr("services.joidy_vault_writer.get_vault_path", lambda: tmp_path)
    goal = _goal(db_session, title="fail-me")
    db_session.commit()

    resp = client.post(f"/goals/{goal.id}/fail")
    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"
    # fail_goal wrote the vault file
    assert list((tmp_path / "Objetivos").glob(f"{goal.id}_*.md"))

    assert client.post("/goals/999999/fail").status_code == 404

    resp = client.delete(f"/goals/{goal.id}")
    assert resp.status_code == 204
    assert client.get(f"/goals/{goal.id}").status_code == 404
    assert client.delete("/goals/999999").status_code == 404


def test_resolve_removal_actions(client, db_session):
    del_goal = _goal(db_session, title="del", pending_removal=True)
    man_goal = _goal(db_session, title="man", pending_removal=True)
    can_goal = _goal(db_session, title="can", pending_removal=True)
    plain = _goal(db_session, title="plain")
    db_session.commit()

    # Invalid action rejected by the Literal whitelist
    assert client.post(f"/goals/{del_goal.id}/resolve-removal", json={"action": "bogus"}).status_code == 422

    resp = client.post(f"/goals/{del_goal.id}/resolve-removal", json={"action": "delete"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}
    assert db_session.get(Goal, del_goal.id) is None

    resp = client.post(f"/goals/{man_goal.id}/resolve-removal", json={"action": "manual"})
    assert resp.status_code == 200
    assert resp.json()["pending_removal"] is False

    resp = client.post(f"/goals/{can_goal.id}/resolve-removal", json={"action": "cancel"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "CANCELLED"

    # Goal without pending_removal still resolves (clears the flag, keeps row)
    resp = client.post(f"/goals/{plain.id}/resolve-removal", json={"action": "manual"})
    assert resp.status_code == 200

    # Delete is idempotent: missing goal still reports "deleted"; the
    # non-destructive actions 404 on a missing goal.
    resp = client.post("/goals/999999/resolve-removal", json={"action": "delete"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}
    assert client.post("/goals/999999/resolve-removal", json={"action": "manual"}).status_code == 404
    assert client.post("/goals/999999/resolve-removal", json={"action": "cancel"}).status_code == 404


# ─── unwritable vault (#1478) ─────────────────────────────────────────────────


def _raise_permission(*_args, **_kwargs):
    raise PermissionError("vault is read-only")


def test_create_goal_vault_unwritable_still_creates(client, db_session, monkeypatch):
    """#1478 — get_objectives_dir() raising PermissionError must not 500:
    the goal is created anyway and ``source_path`` stays null."""
    monkeypatch.setattr("routers.goals.get_objectives_dir", _raise_permission)

    resp = client.post("/goals/", json=_goal_payload(title="unwritable-vault"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["source_path"] is None

    db_session.expire_all()
    goal = db_session.query(Goal).filter(Goal.title == "unwritable-vault").one()
    assert goal.source_path is None


def test_create_goal_file_write_failure_still_creates(client, db_session, monkeypatch, tmp_path):
    """#1478 — the same guard covers a failure inside ``_write_goal_file``
    (e.g. ``Objetivos/`` exists but is read-only, so mkdir succeeds and
    ``write_text`` raises)."""
    monkeypatch.setattr("routers.goals._write_goal_file", _raise_permission)

    resp = client.post("/goals/", json=_goal_payload(title="half-writable"))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["source_path"] is None
    # The file must not exist either — no bogus source_path for an unwritten file.
    assert not list((tmp_path / "isolated-vault" / "Objetivos").glob(f"{data['id']}_*.md"))

    db_session.expire_all()
    assert db_session.get(Goal, data["id"]).source_path is None


def test_create_goal_writes_vault_file(client, tmp_path):
    """Control: with a writable vault (autouse ``_isolated_vault``) the goal
    file is written and ``source_path`` points at it."""
    resp = client.post("/goals/", json=_goal_payload(title="vault-goal"))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["source_path"] == f"Objetivos/{data['id']}_vault-goal.md"

    files = list((tmp_path / "isolated-vault" / "Objetivos").glob(f"{data['id']}_*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "joidy_managed: True" in body
    assert "# vault-goal" in body


def test_fail_and_delete_goal_vault_unwritable(client, db_session, monkeypatch):
    """#1478 — the same audit applies to the other vault-write call sites:
    /fail and DELETE must succeed even when the vault write blows up."""
    monkeypatch.setattr("routers.goals.get_objectives_dir", _raise_permission)
    # delete_goal_file resolves the objectives dir inside joidy_vault_writer.
    monkeypatch.setattr("services.joidy_vault_writer.get_objectives_dir", _raise_permission)
    goal = _goal(db_session, title="fail-anyway")
    db_session.commit()

    resp = client.post(f"/goals/{goal.id}/fail")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "FAILED"

    assert client.delete(f"/goals/{goal.id}").status_code == 204
    assert client.get(f"/goals/{goal.id}").status_code == 404
