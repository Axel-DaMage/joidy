"""Extra coverage for ``routers/notes.py`` (#1401).

Existing note tests cover plain CRUD; this file pins the paths they miss:
input validators, list filters, bulk operations, backlinks, the semantic
search and similar-notes pgvector endpoints, and the embedding dead-letter
queue endpoints. Vector queries are PostgreSQL-only and skip on the SQLite
fallback.
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from models.note import EmbeddingFailure, Note, NoteEmbedding, NoteLink, NoteTag, Tag
from routers.notes import _clean_tag_list

_IS_PG = os.environ.get("DATABASE_URL", "").startswith("postgresql")
_pg_only = pytest.mark.skipif(not _IS_PG, reason="pgvector cosine operator requires PostgreSQL")


def _note(db, title="Extra note", **kwargs) -> Note:
    note = Note(title=title, content=kwargs.pop("content", "body"), source="joidy", **kwargs)
    db.add(note)
    db.flush()
    return note


def _tag(db, name) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.flush()
    return tag


def _failure(db, note_id, attempts=1, **kwargs) -> EmbeddingFailure:
    kwargs.setdefault("last_error", "boom")
    failure = EmbeddingFailure(note_id=note_id, attempts=attempts, **kwargs)
    db.add(failure)
    db.flush()
    return failure


def _mock_embed_client(json_data):
    """Mock ``routers.notes.http_client`` returning ``json_data`` from POST."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(return_value=mock_resp)
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return mock_instance


# ─── Validators ───────────────────────────────────────────────────────────────


def test_clean_tag_list_normalizes_dedupes_and_skips_non_strings():
    assert _clean_tag_list([123, None, "  My Tag  ", "", "my tag", "other"]) == ["my tag", "other"]


def test_create_note_rejects_unknown_source(client):
    resp = client.post("/notes/", json={"title": "x", "source": "bogus"})
    assert resp.status_code == 422


def test_update_note_validators_accept_explicit_nulls(client, db_session):
    note = _note(db_session, "validator-note")
    db_session.commit()

    # Explicit nulls exercise the ``v is None`` early-returns in NoteUpdate.
    resp = client.put(
        f"/notes/{note.id}",
        json={"title": None, "content": None, "tags": None, "source": None},
    )
    assert resp.status_code == 200


def test_update_note_rejects_too_many_tags(client, db_session):
    note = _note(db_session, "many-tags-note")
    db_session.commit()
    resp = client.put(f"/notes/{note.id}", json={"tags": [f"t{i}" for i in range(51)]})
    assert resp.status_code == 422


def test_update_note_rejects_bad_source(client, db_session):
    note = _note(db_session, "bad-source-note")
    db_session.commit()
    resp = client.put(f"/notes/{note.id}", json={"source": "bogus"})
    assert resp.status_code == 422


def test_create_note_blank_source_path_is_ignored(client, db_session):
    """A whitespace-only source_path normalizes to None → accepted as absent."""
    resp = client.post("/notes/", json={"title": "blank-path", "source_path": "   "})
    assert resp.status_code == 201


# ─── list_notes filters ───────────────────────────────────────────────────────


def test_list_notes_filters_by_tag_and_source_path(client, db_session):
    tag = _tag(db_session, "filter-tag")
    tagged = _note(db_session, "tagged", source_path="/vault/tagged.md")
    plain = _note(db_session, "plain", source_path="/vault/plain.md")
    db_session.add(NoteTag(note_id=tagged.id, tag_id=tag.id))
    db_session.commit()

    by_tag = client.get("/notes/", params={"tag": "filter-tag"})
    assert by_tag.status_code == 200
    ids = {n["id"] for n in by_tag.json()}
    assert tagged.id in ids
    assert plain.id not in ids

    by_path = client.get("/notes/", params={"source_path": "/vault/plain.md"})
    assert by_path.status_code == 200
    ids = {n["id"] for n in by_path.json()}
    assert ids == {plain.id}


# ─── update/delete 404s and bulk ops ──────────────────────────────────────────


def test_update_missing_note_404(client):
    resp = client.put("/notes/999999", json={"title": "nope"})
    assert resp.status_code == 404


def test_delete_missing_note_404(client):
    resp = client.delete("/notes/999999")
    assert resp.status_code == 404


def test_bulk_delete_counts_only_existing(client, db_session):
    note = _note(db_session, "bulk-del")
    db_session.commit()
    resp = client.post("/notes/bulk-delete", json={"ids": [note.id, 999999]})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1, "total": 2}


def test_bulk_untag_removes_matching_links(client, db_session):
    tag = _tag(db_session, "untag-me")
    note = _note(db_session, "untag-note")
    other = _note(db_session, "untag-other")
    db_session.add_all(
        [
            NoteTag(note_id=note.id, tag_id=tag.id),
            NoteTag(note_id=other.id, tag_id=tag.id),
        ]
    )
    db_session.commit()

    resp = client.post(
        "/notes/bulk-untag",
        json={"ids": [note.id, other.id, 999999], "tags": ["untag-me", "no-such-tag"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["removed"] == 2
    assert data["notes"] == 3
    assert db_session.query(NoteTag).filter(NoteTag.tag_id == tag.id).count() == 0


def test_bulk_tag_adds_missing_links(client, db_session):
    note = _note(db_session, "bulk-tag-note")
    db_session.commit()
    resp = client.post("/notes/bulk-tag", json={"ids": [note.id, 999999], "tags": ["bulk-new-tag"]})
    assert resp.status_code == 200
    assert resp.json()["added"] == 1


# ─── backlinks ────────────────────────────────────────────────────────────────


def test_backlinks_returns_notes_linking_to_target(client, db_session):
    target = _note(db_session, "target-note")
    source = _note(db_session, "source-note")
    unrelated = _note(db_session, "unrelated-note")
    db_session.add(NoteLink(source_note_id=source.id, target_note_id=target.id))
    db_session.add(NoteLink(source_note_id=unrelated.id, target_note_id=source.id))
    db_session.commit()

    resp = client.get(f"/notes/{target.id}/backlinks")
    assert resp.status_code == 200
    data = resp.json()
    assert [n["id"] for n in data] == [source.id]


def test_backlinks_missing_note_404(client):
    resp = client.get("/notes/999999/backlinks")
    assert resp.status_code == 404


# ─── semantic search ──────────────────────────────────────────────────────────


def test_semantic_search_disabled(client, monkeypatch):
    monkeypatch.setattr("config.settings.ai_service_enabled", False)
    resp = client.post("/notes/search/semantic", json={"query": "hello"})
    assert resp.status_code == 503


def test_semantic_search_blank_query(client):
    resp = client.post("/notes/search/semantic", json={"query": "   "})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_semantic_search_embed_failure(client):
    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("ai down"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    with patch("routers.notes.http_client", return_value=mock_instance):
        resp = client.post("/notes/search/semantic", json={"query": "hello"})
    assert resp.status_code == 503


def test_semantic_search_empty_embedding(client):
    with patch("routers.notes.http_client", return_value=_mock_embed_client({"embedding": None})):
        resp = client.post("/notes/search/semantic", json={"query": "hello"})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


@_pg_only
def test_semantic_search_no_matching_embeddings(client, monkeypatch):
    """Embed succeeds but the note_embeddings table is empty → empty results."""
    monkeypatch.setattr("config.settings.internal_secret", "test-secret")
    vec = [0.5] * 768
    with patch("routers.notes.http_client", return_value=_mock_embed_client({"embedding": vec})):
        resp = client.post("/notes/search/semantic", json={"query": "hello", "limit": 5})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


@_pg_only
def test_semantic_search_returns_similar_notes(client, db_session):
    vec = [0.25] * 768
    # Near-identical but not identical: keeps a strictly larger cosine
    # distance so the exact match always sorts first.
    near = vec[:-1] + [0.26]
    note = _note(db_session, "semantic-hit")
    other = _note(db_session, "semantic-other")
    db_session.add(NoteEmbedding(note_id=note.id, embedding=vec))
    db_session.add(NoteEmbedding(note_id=other.id, embedding=near))
    db_session.commit()

    with patch("routers.notes.http_client", return_value=_mock_embed_client({"embedding": vec})):
        resp = client.post("/notes/search/semantic", json={"query": "hello", "limit": 5, "threshold": 0.5})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    # Identical vectors → cosine distance ~0 → similarity ~1.0, sorted first.
    assert results[0]["note"]["id"] == note.id
    assert results[0]["score"] == pytest.approx(1.0)
    assert results[1]["note"]["id"] == other.id


# ─── similar notes ────────────────────────────────────────────────────────────


def test_similar_notes_missing_404(client):
    resp = client.get("/notes/999999/similar")
    assert resp.status_code == 404


def test_similar_notes_without_embedding_returns_empty(client, db_session):
    note = _note(db_session, "no-embedding")
    db_session.commit()
    resp = client.get(f"/notes/{note.id}/similar")
    assert resp.status_code == 200
    assert resp.json() == []


@_pg_only
def test_similar_notes_returns_neighbors(client, db_session):
    vec = [1.0] + [0.0] * 767
    note = _note(db_session, "anchor")
    neighbor = _note(db_session, "neighbor")
    far = _note(db_session, "far-away")
    db_session.add(NoteEmbedding(note_id=note.id, embedding=vec))
    db_session.add(NoteEmbedding(note_id=neighbor.id, embedding=[1.0] + [0.0] * 767))
    db_session.add(NoteEmbedding(note_id=far.id, embedding=[0.0] * 767 + [1.0]))
    db_session.commit()

    resp = client.get(f"/notes/{note.id}/similar", params={"limit": 5})
    assert resp.status_code == 200
    results = resp.json()
    ids = [r["note"]["id"] for r in results]
    # The anchor itself is excluded; both other embedded notes come back,
    # nearest first.
    assert note.id not in ids
    assert ids[0] == neighbor.id
    assert far.id in ids


@_pg_only
def test_similar_notes_empty_when_no_other_embeddings(client, db_session):
    note = _note(db_session, "lone-embedding")
    db_session.add(NoteEmbedding(note_id=note.id, embedding=[0.5] * 768))
    db_session.commit()
    resp = client.get(f"/notes/{note.id}/similar")
    assert resp.status_code == 200
    assert resp.json() == []


# ─── embedding retry / dead-letter endpoints ──────────────────────────────────


def test_retry_failed_embeddings_queues_notes(client, db_session, monkeypatch):
    note = _note(db_session, "retry-me")
    _failure(db_session, note.id, attempts=1, next_retry_at=datetime.now(UTC) - timedelta(minutes=1))
    dead_note = _note(db_session, "dead-me")
    _failure(db_session, dead_note.id, attempts=99)
    db_session.commit()

    mock_trigger = MagicMock()
    monkeypatch.setattr("routers.notes.trigger_embedding", mock_trigger)
    resp = client.post("/notes/embeddings/retry-failed", params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued"] == 1
    assert data["remaining_failures"] == 2
    mock_trigger.assert_called_once_with(note.id, note.content)


def test_list_dead_letters_returns_titles(client, db_session):
    note = _note(db_session, "dead-letter-note")
    _failure(db_session, note.id, attempts=99, last_error="https://internal.example/path leaked")
    db_session.commit()

    resp = client.get("/notes/embeddings/dead-letters")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["note_id"] == note.id
    assert entries[0]["note_title"] == "dead-letter-note"
    # URLs/paths are redacted before the value reaches the API (#1332).
    assert "internal.example" not in entries[0]["last_error"]


def test_reset_dead_letter_entry(client, db_session):
    note = _note(db_session, "reset-me")
    _failure(db_session, note.id, attempts=99)
    db_session.commit()

    resp = client.post(f"/notes/embeddings/dead-letters/{note.id}/reset")
    assert resp.status_code == 200
    assert resp.json() == {"status": "reset", "note_id": note.id}

    failure = db_session.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note.id).first()
    assert failure.attempts == 0


def test_reset_missing_dead_letter_404(client):
    resp = client.post("/notes/embeddings/dead-letters/999999/reset")
    assert resp.status_code == 404


def test_purge_dead_letters(client, db_session):
    note = _note(db_session, "purge-me")
    _failure(db_session, note.id, attempts=99)
    retryable_note = _note(db_session, "keep-me")
    _failure(db_session, retryable_note.id, attempts=1)
    db_session.commit()

    resp = client.delete("/notes/embeddings/dead-letters")
    assert resp.status_code == 200
    assert resp.json() == {"purged": 1}
    assert db_session.query(EmbeddingFailure).count() == 1
