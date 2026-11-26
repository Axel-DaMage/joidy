"""Regression tests for #1520 — batched bulk note endpoints.

``bulk-tag`` / ``bulk-untag`` / ``bulk-delete`` used to loop per note,
issuing per-item SELECTs/INSERTs/DELETEs plus one commit per note — up to
~50k round trips on a 500-note request. These tests pin the preserved
semantics (partial success, response counts, derived-data resync, XP
revert) and bound the emitted statement count to a constant that does not
scale with batch size.
"""

import contextlib

from fastapi.testclient import TestClient
from models.gamification import UserStats, XPEvent
from models.note import Note, NoteTag, Tag, TagCooccurrence
from services.gamification_engine import xp_for
from sqlalchemy import event
from sqlalchemy.orm import Session

# Generous upper bounds for the DML statements a bulk request may emit.
# The batched implementation stays ~10-15 statements regardless of batch
# size; the old per-item loop emitted hundreds-to-thousands.
BULK_TAG_MAX_STATEMENTS = 25
BULK_UNTAG_MAX_STATEMENTS = 25
BULK_DELETE_MAX_STATEMENTS = 35


@contextlib.contextmanager
def _count_statements(engine):
    """Yield a list collecting DML statements issued through the engine."""
    statements = []

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def _seed_notes(db_session: Session, count: int) -> list[Note]:
    notes = [Note(title=f"bulk-{i}", content=f"content {i}", source="joidy") for i in range(count)]
    db_session.add_all(notes)
    db_session.flush()
    return notes


def _attach_tag(db_session: Session, note_id: int, name: str, source: str = "manual") -> Tag:
    tag = db_session.query(Tag).filter(Tag.name == name).first()
    if tag is None:
        tag = Tag(name=name)
        db_session.add(tag)
        db_session.flush()
    db_session.add(NoteTag(note_id=note_id, tag_id=tag.id, source=source))
    db_session.flush()
    return tag


# ── POST /notes/bulk-tag ───────────────────────────────────────────────────────


def test_bulk_tag_mixed_valid_and_invalid_ids(client: TestClient, db_session: Session):
    """Missing ids are skipped; existing notes each get every tag."""
    notes = _seed_notes(db_session, 3)
    res = client.post(
        "/notes/bulk-tag",
        json={"ids": [notes[0].id, 999999, notes[1].id, notes[2].id], "tags": ["alpha", "beta"]},
    )
    assert res.status_code == 200
    assert res.json() == {"added": 6, "notes": 4, "tags": ["alpha", "beta"]}
    for note in notes:
        assert db_session.query(NoteTag).filter(NoteTag.note_id == note.id).count() == 2


def test_bulk_tag_skips_existing_associations(client: TestClient, db_session: Session):
    notes = _seed_notes(db_session, 2)
    _attach_tag(db_session, notes[0].id, "alpha")
    res = client.post("/notes/bulk-tag", json={"ids": [n.id for n in notes], "tags": ["alpha"]})
    assert res.status_code == 200
    assert res.json()["added"] == 1
    # No duplicate association row on the already-tagged note.
    assert db_session.query(NoteTag).filter(NoteTag.note_id == notes[0].id).count() == 1


def test_bulk_tag_idempotent_second_run(client: TestClient, db_session: Session):
    notes = _seed_notes(db_session, 2)
    payload = {"ids": [n.id for n in notes], "tags": ["alpha"]}
    assert client.post("/notes/bulk-tag", json=payload).json()["added"] == 2
    res = client.post("/notes/bulk-tag", json=payload)
    assert res.status_code == 200
    assert res.json()["added"] == 0


def test_bulk_tag_duplicate_ids_no_conflict(client: TestClient, db_session: Session):
    """Duplicate ids in the request must not produce a duplicate-PK insert."""
    note = _seed_notes(db_session, 1)[0]
    res = client.post("/notes/bulk-tag", json={"ids": [note.id, note.id], "tags": ["alpha"]})
    assert res.status_code == 200
    assert res.json()["added"] == 1
    assert db_session.query(NoteTag).filter(NoteTag.note_id == note.id).count() == 1


def test_bulk_tag_no_matching_notes_creates_no_tags(client: TestClient, db_session: Session):
    """Tags are only materialized when at least one note exists — same as the
    old loop, where ``get_or_create_tag`` ran inside the note loop."""
    res = client.post("/notes/bulk-tag", json={"ids": [999999], "tags": ["ghost"]})
    assert res.status_code == 200
    assert res.json()["added"] == 0
    assert db_session.query(Tag).filter(Tag.name == "ghost").first() is None


def test_bulk_tag_query_count_bounded(client: TestClient, db_session: Session, _db_engine):
    """60 notes x 10 tags: statement count must stay constant, not O(n*m)."""
    notes = _seed_notes(db_session, 60)
    tags = [f"tag-{i}" for i in range(10)]
    with _count_statements(_db_engine) as statements:
        res = client.post("/notes/bulk-tag", json={"ids": [n.id for n in notes], "tags": tags})
    assert res.status_code == 200
    assert res.json()["added"] == 600
    assert len(statements) <= BULK_TAG_MAX_STATEMENTS


# ── POST /notes/bulk-untag ─────────────────────────────────────────────────────


def test_bulk_untag_removes_only_existing_associations(client: TestClient, db_session: Session):
    notes = _seed_notes(db_session, 3)
    _attach_tag(db_session, notes[0].id, "alpha")
    _attach_tag(db_session, notes[1].id, "alpha")
    _attach_tag(db_session, notes[2].id, "beta")
    res = client.post(
        "/notes/bulk-untag",
        json={"ids": [n.id for n in notes] + [999999], "tags": ["alpha", "beta"]},
    )
    assert res.status_code == 200
    assert res.json() == {"removed": 3, "notes": 4, "tags": ["alpha", "beta"]}
    assert db_session.query(NoteTag).count() == 0


def test_bulk_untag_unknown_tag_is_noop(client: TestClient, db_session: Session):
    note = _seed_notes(db_session, 1)[0]
    _attach_tag(db_session, note.id, "alpha")
    res = client.post("/notes/bulk-untag", json={"ids": [note.id], "tags": ["nonexistent"]})
    assert res.status_code == 200
    assert res.json()["removed"] == 0
    # The unrelated association survives.
    assert db_session.query(NoteTag).filter(NoteTag.note_id == note.id).count() == 1


def test_bulk_untag_query_count_bounded(client: TestClient, db_session: Session, _db_engine):
    notes = _seed_notes(db_session, 60)
    tags = [f"tag-{i}" for i in range(10)]
    tag_objs = [Tag(name=t) for t in tags]
    db_session.add_all(tag_objs)
    db_session.flush()
    db_session.add_all(NoteTag(note_id=note.id, tag_id=tag.id, source="manual") for note in notes for tag in tag_objs)
    db_session.flush()
    with _count_statements(_db_engine) as statements:
        res = client.post("/notes/bulk-untag", json={"ids": [n.id for n in notes], "tags": tags})
    assert res.status_code == 200
    assert res.json()["removed"] == 600
    assert len(statements) <= BULK_UNTAG_MAX_STATEMENTS


# ── POST /notes/bulk-delete ────────────────────────────────────────────────────


def test_bulk_delete_mixed_valid_and_invalid_ids(client: TestClient, db_session: Session):
    notes = _seed_notes(db_session, 3)
    # The endpoint's commit expires ORM objects still in this session, so the
    # ids must be captured before the request (touching a deleted note's
    # attributes afterwards would raise ObjectDeletedError).
    n0, n1, n2 = [n.id for n in notes]
    res = client.post("/notes/bulk-delete", json={"ids": [n0, 999999, n1]})
    assert res.status_code == 200
    assert res.json() == {"deleted": 2, "total": 3}
    assert db_session.query(Note).filter(Note.id == n0).first() is None
    assert db_session.query(Note).filter(Note.id == n1).first() is None
    assert db_session.query(Note).filter(Note.id == n2).first() is not None
    assert client.get(f"/notes/{n0}").status_code == 404


def test_bulk_delete_duplicate_ids_counted_once(client: TestClient, db_session: Session):
    note_id = _seed_notes(db_session, 1)[0].id
    res = client.post("/notes/bulk-delete", json={"ids": [note_id, note_id]})
    assert res.status_code == 200
    assert res.json() == {"deleted": 1, "total": 2}
    assert db_session.query(Note).filter(Note.id == note_id).first() is None


def test_bulk_delete_removes_tag_associations_and_resyncs(client: TestClient, db_session: Session):
    """Deleting both notes sharing a tag pair must drop the pair from the
    co-occurrence table (weight falls below the >= 2 threshold)."""
    notes = _seed_notes(db_session, 2)
    for note in notes:
        _attach_tag(db_session, note.id, "t1")
        _attach_tag(db_session, note.id, "t2")
    from services.tag_graph import sync_tag_cooccurrences_for_tags

    sync_tag_cooccurrences_for_tags(db_session, {t.id for t in db_session.query(Tag).all()})
    assert db_session.query(TagCooccurrence).count() == 1

    res = client.post("/notes/bulk-delete", json={"ids": [n.id for n in notes]})
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    assert db_session.query(NoteTag).count() == 0
    assert db_session.query(TagCooccurrence).count() == 0


def test_bulk_delete_reverts_xp_once_per_note(client: TestClient, db_session: Session):
    notes = _seed_notes(db_session, 3)
    db_session.add(UserStats(id=1, total_xp=100))
    db_session.flush()
    xp = xp_for("note_created", db_session, 10)

    res = client.post("/notes/bulk-delete", json={"ids": [n.id for n in notes]})
    assert res.status_code == 200
    assert res.json()["deleted"] == 3

    stats = db_session.query(UserStats).filter(UserStats.id == 1).one()
    assert stats.total_xp == 100 - 3 * xp
    events = db_session.query(XPEvent).filter(XPEvent.event_type == "note_deleted").all()
    assert len(events) == 3
    assert all(e.xp == -xp for e in events)


def test_bulk_delete_xp_floor_at_zero(client: TestClient, db_session: Session):
    """The aggregated revert clamps at 0, same as sequential per-note clamps."""
    notes = _seed_notes(db_session, 3)
    db_session.add(UserStats(id=1, total_xp=5))
    db_session.flush()
    res = client.post("/notes/bulk-delete", json={"ids": [n.id for n in notes]})
    assert res.status_code == 200
    assert db_session.query(UserStats).filter(UserStats.id == 1).one().total_xp == 0


def test_bulk_delete_no_matches(client: TestClient, db_session: Session):
    res = client.post("/notes/bulk-delete", json={"ids": [999998, 999999]})
    assert res.status_code == 200
    assert res.json() == {"deleted": 0, "total": 2}


def test_bulk_delete_query_count_bounded(client: TestClient, db_session: Session, _db_engine):
    notes = _seed_notes(db_session, 60)
    for note in notes:
        _attach_tag(db_session, note.id, "shared")
    db_session.add(UserStats(id=1, total_xp=10000))
    db_session.flush()
    with _count_statements(_db_engine) as statements:
        res = client.post("/notes/bulk-delete", json={"ids": [n.id for n in notes]})
    assert res.status_code == 200
    assert res.json()["deleted"] == 60
    assert len(statements) <= BULK_DELETE_MAX_STATEMENTS
