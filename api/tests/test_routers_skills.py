"""Router tests for the skills endpoints (#1001).

Covers:
- GET /skills/ — list shape and content.
- GET /skills/tree — nested nodes/edges shape for the D3 visualization,
  including parent-tag edges.
- POST /skills/sync — recalculation from note/tag counts and cache
  invalidation after mutation.

The skills list/tree handlers are ttl_cache'd in-process, so each test clears
the registered caches to avoid leaking state between tests.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from models.note import Note
from models.note import Tag as TagModel
from models.skill import Skill
from services.response_cache import clear_api_caches


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_api_caches()
    yield
    clear_api_caches()


def _tag(db_session, name=None) -> TagModel:
    tag = TagModel(name=name or f"tag-skills-{uuid.uuid4().hex[:8]}")
    db_session.add(tag)
    db_session.commit()
    return tag


def test_list_skills_empty(client: TestClient):
    response = client.get("/skills/")
    assert response.status_code == 200
    assert response.json() == []


def test_list_skills_shape_and_locked_filtered(client: TestClient, db_session):
    tag = _tag(db_session)
    locked_tag = _tag(db_session)
    db_session.add_all(
        [
            Skill(tag_id=tag.id, note_count=5, level="apprentice"),
            Skill(tag_id=locked_tag.id, note_count=0, level="locked"),
        ]
    )
    db_session.commit()

    response = client.get("/skills/")
    assert response.status_code == 200
    skills = response.json()
    assert all(s["level"] != "locked" for s in skills)
    mine = next(s for s in skills if s["tag_id"] == tag.id)
    for key in ("id", "tag_id", "tag_name", "level", "note_count", "first_unlocked_at"):
        assert key in mine
    assert mine["tag_name"] == tag.name
    assert mine["note_count"] == 5


def test_skill_tree_empty(client: TestClient):
    response = client.get("/skills/tree")
    assert response.status_code == 200
    data = response.json()
    assert data["nodes"] == []
    assert data["edges"] == []


def test_skill_tree_nodes_and_parent_edges(client: TestClient, db_session):
    parent = _tag(db_session)
    child = TagModel(name=f"tag-skills-child-{uuid.uuid4().hex[:8]}", parent_id=parent.id)
    db_session.add(child)
    db_session.commit()
    db_session.add_all(
        [
            Skill(tag_id=parent.id, note_count=30, level="expert"),
            Skill(tag_id=child.id, note_count=5, level="apprentice"),
        ]
    )
    db_session.commit()

    response = client.get("/skills/tree")
    assert response.status_code == 200
    data = response.json()

    node_by_id = {n["id"]: n for n in data["nodes"]}
    assert parent.id in node_by_id and child.id in node_by_id
    assert node_by_id[child.id]["name"] == child.name
    assert node_by_id[child.id]["level"] == "apprentice"
    for key in ("id", "name", "level", "note_count", "xp"):
        assert key in node_by_id[child.id]

    edge = {"source": parent.id, "target": child.id}
    assert edge in data["edges"]


def _link_notes(db_session, tag: TagModel, count: int):
    """Create `count` notes tagged with `tag` (>=3 needed for a non-locked skill)."""
    from models.note import NoteTag

    for _ in range(count):
        note = Note(title=f"n-skills-{uuid.uuid4().hex[:8]}", content="x")
        db_session.add(note)
        db_session.flush()
        db_session.add(NoteTag(note_id=note.id, tag_id=tag.id))
    db_session.commit()


def test_sync_skills_creates_and_updates(client: TestClient, db_session):
    """Sync derives skill note_count/level from NoteTag rows."""
    tag = _tag(db_session)
    _link_notes(db_session, tag, 3)  # <3 counts stay "locked" and are filtered

    response = client.post("/skills/sync")
    assert response.status_code == 200
    data = response.json()
    assert "synced" in data and "updates" in data
    assert any(u["tag_id"] == tag.id for u in data["updates"])

    skills = client.get("/skills/").json()
    mine = next(s for s in skills if s["tag_id"] == tag.id)
    assert mine["note_count"] == 3
    assert mine["level"] == "apprentice"


def test_sync_invalidates_list_cache(client: TestClient, db_session):
    """POST /skills/sync clears the ttl-cached list so new skills appear."""
    client.get("/skills/")  # warm the cache

    tag = _tag(db_session)
    # Seed the skill AND the notes that keep it non-locked through re-sync.
    db_session.add(Skill(tag_id=tag.id, note_count=3, level="apprentice"))
    db_session.commit()
    _link_notes(db_session, tag, 3)

    # Without invalidation the cached list would hide the new row.
    response = client.post("/skills/sync")
    assert response.status_code == 200

    skills = client.get("/skills/").json()
    assert any(s["tag_id"] == tag.id for s in skills)
