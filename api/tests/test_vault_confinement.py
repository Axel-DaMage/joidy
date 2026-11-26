"""Security tests — note ``source_path`` confinement (#1287, #1314).

Covers:
- ``resolve_confined_source_path`` — the shared realpath/commonpath +
  denylist boundary used by ``write_to_vault`` and
  ``sync_service.resolve_conflict(keep_remote)``;
- ``write_to_vault`` — prefix confusion and planted-symlink write escapes;
- ``resolve_conflict(keep_remote)`` — read-exfil through a symlink or a
  denylisted path, plus the no-oracle generic error string;
- ``POST/PUT /notes`` — router-level ``source_path`` validation (``.obsidian``
  ``_joidy``, outside-vault, clobbering an unclaimed existing file);
- ``POST /webhook/obsidian`` + ``/legacy`` — conflict-flag writes are
  fail-closed unless ``OBSIDIAN_WEBHOOK_SECRET`` is configured and presented.
"""

import os
from datetime import UTC, datetime

import pytest
from config import settings
from fastapi.testclient import TestClient
from models.note import Note
from models.sync_state import SyncState
from services.note_service import write_to_vault
from services.sync_service import resolve_conflict
from services.vault_paths import normalize_source_path, resolve_confined_source_path


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """A real on-disk vault dir wired as the effective vault path."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    monkeypatch.setattr(settings, "obsidian_vault_path", str(vault_dir))
    return vault_dir


@pytest.fixture
def vault_headers(worker_headers):
    """Auth + trust headers the vault worker sends (#1332)."""
    return {**worker_headers, "X-From-Vault": "1"}


def _conflicted_note(db_session, source_path):
    note = Note(title="Conflicted", content="local content", source="obsidian", source_path=source_path)
    db_session.add(note)
    db_session.flush()
    sync = SyncState(
        note_id=note.id,
        conflict=True,
        local_mtime=datetime(2024, 1, 1, tzinfo=UTC),
        remote_mtime=datetime(2024, 1, 2, tzinfo=UTC),
    )
    db_session.add(sync)
    db_session.commit()
    return note


# ── resolve_confined_source_path ──────────────────────────────────────────────


def test_confined_legit_vault_file(vault):
    target = vault / "note.md"
    target.write_text("# hi")
    assert resolve_confined_source_path(str(target)) == os.path.realpath(target)


def test_confined_nonexistent_file_inside_vault(vault):
    """Writes create files — a not-yet-existing .md inside the vault is fine."""
    resolved = resolve_confined_source_path(str(vault / "new.md"))
    assert resolved == os.path.realpath(vault / "new.md")


def test_confined_prefix_confusion_refused(vault, tmp_path):
    """#1287: ``/vault_evil/x`` must not pass for vault ``/vault``."""
    evil = tmp_path / "vault_evil"
    evil.mkdir()
    target = evil / "x.md"
    target.write_text("evil")
    assert resolve_confined_source_path(str(target)) is None


def test_confined_traversal_refused(vault):
    assert resolve_confined_source_path(str(vault / ".." / "escape.md")) is None
    assert resolve_confined_source_path(f"{vault}/../../etc/passwd") is None


def test_confined_symlink_escape_refused(vault, tmp_path):
    """#1287: a symlink inside the vault pointing outside must be refused."""
    outside = tmp_path / "outside.md"
    outside.write_text("secret")
    link = vault / "link.md"
    link.symlink_to(outside)
    assert resolve_confined_source_path(str(link)) is None


def test_confined_symlink_inside_vault_allowed(vault):
    real = vault / "real.md"
    real.write_text("real")
    link = vault / "alias.md"
    link.symlink_to(real)
    assert resolve_confined_source_path(str(link)) == os.path.realpath(real)


def test_confined_obsidian_dir_refused(vault):
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir()
    target = obsidian_dir / "app.json"
    target.write_text("{}")
    assert resolve_confined_source_path(str(target)) is None


def test_confined_joidy_dir_refused(vault):
    joidy_dir = vault / "_joidy"
    joidy_dir.mkdir()
    target = joidy_dir / "daily.md"
    target.write_text("state")
    assert resolve_confined_source_path(str(target)) is None


def test_confined_hidden_dir_and_dotfile_refused(vault):
    hidden = vault / ".git"
    hidden.mkdir()
    (hidden / "config.md").write_text("x")
    assert resolve_confined_source_path(str(hidden / "config.md")) is None
    assert resolve_confined_source_path(str(vault / ".hidden.md")) is None


def test_confined_non_markdown_refused(vault):
    target = vault / "file.pdf"
    target.write_bytes(b"%PDF")
    assert resolve_confined_source_path(str(target)) is None
    # …but allowed when markdown is not required.
    assert resolve_confined_source_path(str(target), require_markdown=False) == os.path.realpath(target)


def test_confined_vault_root_itself_refused(vault):
    assert resolve_confined_source_path(str(vault)) is None


def test_confined_no_vault_configured(monkeypatch):
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    assert resolve_confined_source_path("/vault/x.md") is None


# ── normalize_source_path — vault-relative anchoring ─────────────────────────


def test_normalize_relative_path_anchors_under_vault(vault):
    """The file-tree move UI sends ``folder/note.md`` — it must land on the
    canonical vault domain, not a cwd-relative stranger."""
    assert normalize_source_path("folder/note.md") == f"{vault}/folder/note.md"


def test_normalize_relative_traversal_stays_outside(vault):
    anchored = normalize_source_path("../escape.md")
    assert anchored is not None
    assert resolve_confined_source_path(anchored) is None


# ── write_to_vault ────────────────────────────────────────────────────────────


def _note_with_path(db_session, source_path, content="note content"):
    note = Note(title="T", content=content, source="joidy", source_path=source_path)
    db_session.add(note)
    db_session.commit()
    return note


def test_write_to_vault_legit_write_works(db_session, vault):
    """A confined vault .md write must still work — content hits disk."""
    note = _note_with_path(db_session, str(vault / "ok.md"), content="hello vault")
    assert write_to_vault(note) is True
    assert (vault / "ok.md").read_text() == "hello vault"


def test_write_to_vault_prefix_confusion_refused(db_session, vault, tmp_path):
    """#1287 verification: ``/vaultX/evil.md`` write is refused."""
    evil_dir = tmp_path / "vaultX"
    evil_dir.mkdir()
    target = evil_dir / "evil.md"
    note = _note_with_path(db_session, str(target))
    assert write_to_vault(note) is False
    assert not target.exists()


def test_write_to_vault_symlink_escape_refused(db_session, vault, tmp_path):
    """#1287 verification: ``vault/x -> outside`` write never leaves the vault."""
    outside = tmp_path / "outside.md"
    outside.write_text("original")
    link = vault / "x.md"
    link.symlink_to(outside)
    note = _note_with_path(db_session, str(link), content="pwned")
    assert write_to_vault(note) is False
    assert outside.read_text() == "original"


def test_write_to_vault_obsidian_dir_refused(db_session, vault):
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir()
    target = obsidian_dir / "app.json.md"
    note = _note_with_path(db_session, str(target))
    assert write_to_vault(note) is False
    assert not target.exists()


def test_write_to_vault_joidy_dir_refused(db_session, vault):
    note = _note_with_path(db_session, str(vault / "_joidy" / "state.md"))
    assert write_to_vault(note) is False


# ── resolve_conflict(keep_remote) — read exfil ────────────────────────────────


def test_keep_remote_symlink_escape_refused(db_session, vault, tmp_path):
    """#1314 verification: ``vault/x -> outside`` + keep_remote copies nothing."""
    outside = tmp_path / "outside-secret.md"
    outside.write_text("SECRET-DATA")
    link = vault / "link.md"
    link.symlink_to(outside)
    note = _conflicted_note(db_session, str(link))

    result = resolve_conflict(db_session, note.id, "keep_remote")

    assert result["status"] == "error"
    assert result["message"] == "Cannot read remote vault file"
    db_session.refresh(note)
    assert note.content == "local content"
    sync = db_session.query(SyncState).filter_by(note_id=note.id).first()
    assert sync.conflict is True  # untouched — the caller decides what to do next


def test_keep_remote_obsidian_dir_refused(db_session, vault):
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "app.json").write_text("{}")
    note = _conflicted_note(db_session, str(obsidian_dir / "app.json"))

    result = resolve_conflict(db_session, note.id, "keep_remote")

    assert result["status"] == "error"
    db_session.refresh(note)
    assert note.content == "local content"


def test_keep_remote_missing_file_no_oracle(db_session, vault):
    """A missing file and a refused file must return the same message (#1314)."""
    note = _conflicted_note(db_session, str(vault / "does-not-exist.md"))
    result = resolve_conflict(db_session, note.id, "keep_remote")
    assert result["status"] == "error"
    assert result["message"] == "Cannot read remote vault file"
    assert "does-not-exist" not in result["message"]
    assert "Errno" not in result["message"]


def test_keep_remote_legit_file_still_works(db_session, vault):
    target = vault / "remote.md"
    target.write_text("remote wins")
    note = _conflicted_note(db_session, str(target))

    result = resolve_conflict(db_session, note.id, "keep_remote")

    assert result["status"] == "ok"
    db_session.refresh(note)
    assert note.content == "remote wins"


# ── POST /notes router validation ─────────────────────────────────────────────


def test_post_note_obsidian_path_rejected(client: TestClient, db_session, vault):
    """#1314 verification: ``source_path=/vault/.obsidian/app.json`` → 400."""
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir()
    app_json = obsidian_dir / "app.json"
    app_json.write_text('{"orig": true}')

    resp = client.post(
        "/notes/",
        json={
            "title": "evil-obsidian-check",
            "content": "corrupted",
            "source_path": str(app_json),
        },
    )

    assert resp.status_code == 400
    assert app_json.read_text() == '{"orig": true}'
    assert db_session.query(Note).filter(Note.title == "evil-obsidian-check").first() is None


def test_post_note_joidy_dir_rejected(client: TestClient, db_session, vault):
    resp = client.post(
        "/notes/",
        json={
            "title": "evil",
            "content": "x",
            "source_path": str(vault / "_joidy" / "state.md"),
        },
    )
    assert resp.status_code == 400
    assert not (vault / "_joidy").exists()


def test_post_note_outside_vault_rejected(client: TestClient, db_session, vault, tmp_path):
    evil_dir = tmp_path / "vaultX"
    evil_dir.mkdir()
    resp = client.post(
        "/notes/",
        json={
            "title": "evil",
            "content": "x",
            "source_path": str(evil_dir / "evil.md"),
        },
    )
    assert resp.status_code == 400


def test_post_note_hidden_dir_rejected(client: TestClient, db_session, vault):
    resp = client.post(
        "/notes/",
        json={
            "title": "evil",
            "content": "x",
            "source_path": str(vault / ".hidden" / "x.md"),
        },
    )
    assert resp.status_code == 400


def test_post_note_non_markdown_rejected(client: TestClient, db_session, vault):
    resp = client.post(
        "/notes/",
        json={
            "title": "evil",
            "content": "x",
            "source_path": str(vault / "file.txt"),
        },
    )
    assert resp.status_code == 400


def test_post_note_legit_source_path_accepted(client: TestClient, db_session, vault):
    """A clean in-vault .md path still creates the note and writes the file."""
    target = vault / "Daily" / "today.md"
    resp = client.post(
        "/notes/",
        json={
            "title": "today",
            "content": "daily body",
            "source_path": str(target),
        },
    )
    assert resp.status_code == 201
    assert target.read_text() == "daily body"


def test_post_note_relative_source_path_accepted(client: TestClient, db_session, vault):
    """Vault-relative paths (file-tree UI) anchor under the vault root."""
    resp = client.post(
        "/notes/",
        json={
            "title": "rel",
            "content": "relative body",
            "source_path": "rel-folder/note.md",
        },
    )
    assert resp.status_code == 201
    assert (vault / "rel-folder" / "note.md").read_text() == "relative body"


def test_post_note_existing_unclaimed_file_rejected(client: TestClient, db_session, vault):
    """A write-context create may not clobber a vault file no note owns."""
    victim = vault / "victim.md"
    victim.write_text("precious")
    resp = client.post(
        "/notes/",
        json={
            "title": "evil",
            "content": "overwrite",
            "source_path": str(victim),
        },
    )
    assert resp.status_code == 400
    assert victim.read_text() == "precious"


def test_post_note_existing_claimed_file_dedups(client: TestClient, db_session, vault):
    """An existing file already claimed by a note is that note's own file —
    create dedups to the existing note instead of 400-ing (#1099)."""
    target = vault / "claimed.md"
    first = client.post("/notes/", json={"title": "orig", "content": "v1", "source_path": str(target)})
    assert first.status_code == 201
    assert target.read_text() == "v1"

    second = client.post("/notes/", json={"title": "dup", "content": "v2", "source_path": str(target)})
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert target.read_text() == "v1"


def test_post_note_from_vault_existing_file_accepted(client: TestClient, db_session, vault, vault_headers):
    """The vault watcher imports files that already exist on disk — from_vault
    skips the ownership check (no write happens anyway)."""
    target = vault / "watcher.md"
    target.write_text("from obsidian")
    resp = client.post(
        "/notes/",
        json={
            "title": "watcher",
            "content": "from obsidian",
            "source_path": str(target),
        },
        headers=vault_headers,
    )
    assert resp.status_code == 201


def test_x_from_vault_header_ignored_without_internal_token(client: TestClient, db_session, vault):
    """#1332: a regular client may not claim vault provenance — the header is
    ignored, so the request takes the normal write path and the existing
    unclaimed file is protected."""
    target = vault / "watcher.md"
    target.write_text("precious")
    resp = client.post(
        "/notes/",
        json={
            "title": "watcher",
            "content": "from obsidian",
            "source_path": str(target),
        },
        headers={"X-From-Vault": "1"},
    )
    assert resp.status_code == 400
    assert target.read_text() == "precious"


def test_put_note_source_path_to_unclaimed_file_rejected(client: TestClient, db_session, vault):
    """Re-pointing a note at an existing unclaimed file must fail — it would
    arm a write that truncates a file no note owns."""
    create = client.post("/notes/", json={"title": "n", "content": "c", "source_path": str(vault / "mine.md")})
    note_id = create.json()["id"]
    victim = vault / "unclaimed.md"
    victim.write_text("precious")

    resp = client.put(f"/notes/{note_id}", json={"source_path": str(victim)})

    assert resp.status_code == 400
    assert victim.read_text() == "precious"


def test_put_note_source_path_to_other_notes_file_rejected(client: TestClient, db_session, vault):
    other_path = vault / "other.md"
    other = client.post("/notes/", json={"title": "other", "content": "o", "source_path": str(other_path)})
    assert other.status_code == 201

    mine_path = vault / "mine.md"
    mine = client.post("/notes/", json={"title": "mine", "content": "m", "source_path": str(mine_path)})
    note_id = mine.json()["id"]

    resp = client.put(f"/notes/{note_id}", json={"source_path": str(other_path)})
    assert resp.status_code == 400


def test_put_note_source_path_own_file_allowed(client: TestClient, db_session, vault):
    target = vault / "own.md"
    create = client.post("/notes/", json={"title": "own", "content": "c", "source_path": str(target)})
    note_id = create.json()["id"]
    assert target.exists()

    # Re-submitting the same source_path (target = the note's own file) is fine.
    resp = client.put(f"/notes/{note_id}", json={"source_path": str(target)})
    assert resp.status_code == 200


def test_put_note_source_path_new_file_allowed(client: TestClient, db_session, vault):
    target = vault / "a.md"
    create = client.post("/notes/", json={"title": "a", "content": "c", "source_path": str(target)})
    note_id = create.json()["id"]

    new_target = vault / "moved" / "a.md"
    resp = client.put(f"/notes/{note_id}", json={"source_path": str(new_target)})
    assert resp.status_code == 200


def test_put_note_source_path_from_vault_rename_accepted(client: TestClient, db_session, vault, vault_headers):
    """Worker rename flow: target exists on disk, unclaimed — allowed only
    because X-From-Vault means no write happens."""
    old = vault / "old.md"
    create = client.post(
        "/notes/",
        json={"title": "r", "content": "c", "source_path": str(old)},
        headers=vault_headers,
    )
    note_id = create.json()["id"]
    renamed = vault / "renamed.md"
    renamed.write_text("renamed on disk")

    resp = client.put(
        f"/notes/{note_id}",
        json={"source_path": str(renamed), "content": "renamed on disk"},
        headers=vault_headers,
    )
    assert resp.status_code == 200


def test_put_note_obsidian_path_rejected(client: TestClient, db_session, vault):
    create = client.post("/notes/", json={"title": "n", "content": "c"})
    note_id = create.json()["id"]
    resp = client.put(
        f"/notes/{note_id}",
        json={"source_path": str(vault / ".obsidian" / "workspace.md")},
    )
    assert resp.status_code == 400


# ── Ownership fast path (#1516) — exact match skips the per-row realpath scan ──


def test_put_note_ownership_exact_match_skips_realpath_scan(client: TestClient, db_session, vault, monkeypatch):
    """#1516: when the target's owner is found by the indexed exact-match
    query, the O(N) per-row realpath scan must not run at all."""
    # Noise rows whose stored paths only resolve through the scan — if the
    # fallback loop runs, each of them gets a realpath call.
    for i in range(25):
        db_session.add(Note(title=f"noise-{i}", content="", source="obsidian", source_path=f"/vault/noise-{i}.md"))
    db_session.commit()

    target = vault / "mine.md"
    create = client.post(
        "/notes/",
        json={"title": "mine", "content": "c", "source_path": str(target)},
    )
    assert create.status_code == 201
    note_id = create.json()["id"]
    assert target.exists()

    import routers.notes as notes_router

    seen: list[str] = []
    delegate = notes_router.resolve_confined_source_path

    def _spy(path, **kwargs):
        seen.append(str(path))
        return delegate(path, **kwargs)

    monkeypatch.setattr(notes_router, "resolve_confined_source_path", _spy)

    resp = client.put(f"/notes/{note_id}", json={"source_path": str(target)})

    assert resp.status_code == 200
    # Only the request path itself plus the single exact-match candidate row
    # are resolved — the O(N) fallback would have resolved every stored row.
    assert len(seen) <= 3
    assert not any(s.startswith("/vault/noise-") for s in seen)


def _aliased_owner_note(db_session):
    """A note whose stored ``source_path`` only matches after realpath — it
    keeps the ``/vault`` domain spelling the watcher writes, so the #1516
    exact-match fast path misses it and the fallback scan must find it."""
    note = Note(title="owner", content="real", source="obsidian", source_path="/vault/real.md")
    db_session.add(note)
    db_session.commit()
    return note


def test_put_note_symlink_alias_of_own_file_allowed(client: TestClient, db_session, vault, monkeypatch):
    """#1516 fallback: a symlink alias pointing at the note's own file still
    resolves to that note through the per-row realpath scan — a spy proves
    the fallback actually ran (the stored ``/vault`` spelling misses the
    exact-match candidates)."""
    real = vault / "real.md"
    real.write_text("real content")
    owner = _aliased_owner_note(db_session)
    alias = vault / "alias.md"
    alias.symlink_to(real)

    import routers.notes as notes_router

    seen: list[str] = []
    delegate = notes_router.resolve_confined_source_path

    def _spy(path, **kwargs):
        seen.append(str(path))
        return delegate(path, **kwargs)

    monkeypatch.setattr(notes_router, "resolve_confined_source_path", _spy)

    resp = client.put(f"/notes/{owner.id}", json={"source_path": str(alias)})

    assert resp.status_code == 200
    assert "/vault/real.md" in seen


def test_put_note_symlink_alias_of_other_notes_file_rejected(client: TestClient, db_session, vault):
    """#1516 fallback: the same alias indirection aimed at *another* note's
    file must still 400 — ownership is by resolved path, not string."""
    real = vault / "real.md"
    real.write_text("precious")
    _aliased_owner_note(db_session)
    create = client.post("/notes/", json={"title": "mine", "content": "c"})
    note_id = create.json()["id"]
    alias = vault / "alias.md"
    alias.symlink_to(real)

    resp = client.put(f"/notes/{note_id}", json={"source_path": str(alias)})

    assert resp.status_code == 400
    assert real.read_text() == "precious"


# ── Obsidian webhooks — conflict-flag writes fail closed (#1314) ──────────────


def _note_with_local_mtime(db_session, source_path="/vault/n.md"):
    """Create a note + SyncState(local_mtime) with an auto-assigned id —
    collision-proof against rows leaked by earlier tests in the session."""
    note = Note(title="N", content="", source="obsidian", source_path=source_path)
    db_session.add(note)
    db_session.flush()
    db_session.add(
        SyncState(
            note_id=note.id,
            local_mtime=datetime.fromtimestamp(1_600_000_000, tz=UTC).replace(tzinfo=None),
            conflict=False,
        )
    )
    db_session.commit()
    return note.id


def test_legacy_webhook_conflict_fail_closed_without_secret(client: TestClient, db_session, monkeypatch):
    """Without OBSIDIAN_WEBHOOK_SECRET the legacy endpoint updates bookkeeping
    but can never arm ``conflict=True`` (#1314)."""
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "")
    monkeypatch.setattr(settings, "auth_password", "")
    note_id = _note_with_local_mtime(db_session)

    resp = client.post(
        "/webhook/obsidian/legacy",
        json={"note_id": note_id, "path": "/vault/n.md", "remote_mtime": 1_700_000_000},
    )

    assert resp.status_code == 200
    assert resp.json()["conflict"] is False
    sync = db_session.query(SyncState).filter_by(note_id=note_id).first()
    assert sync.conflict is False
    # …mtime bookkeeping still runs — only the flag write is gated.
    assert sync.remote_mtime is not None


def test_legacy_webhook_conflict_allowed_with_secret(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "s3cr3t")
    note_id = _note_with_local_mtime(db_session)

    resp = client.post(
        "/webhook/obsidian/legacy?secret=s3cr3t",
        json={"note_id": note_id, "path": "/vault/n.md", "remote_mtime": 1_700_000_000},
    )

    assert resp.status_code == 200
    assert resp.json()["conflict"] is True
    assert db_session.query(SyncState).filter_by(note_id=note_id).first().conflict is True


def test_legacy_webhook_conflict_still_blocked_by_wrong_secret(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "s3cr3t")
    note_id = _note_with_local_mtime(db_session)

    resp = client.post(
        "/webhook/obsidian/legacy?secret=wrong",
        json={"note_id": note_id, "path": "/vault/n.md", "remote_mtime": 1_700_000_000},
    )

    assert resp.status_code == 401
    assert db_session.query(SyncState).filter_by(note_id=note_id).first().conflict is False


def test_webhook_conflict_fail_closed_without_secret(client: TestClient, db_session, monkeypatch):
    """The modern endpoint is gated identically: a mtime-forged update can't
    arm a conflict when no webhook secret is configured (#1314)."""
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "")
    monkeypatch.setattr(settings, "auth_password", "")

    created = client.post(
        "/webhook/obsidian",
        json={"event": "create", "path": "/vault/gated.md", "content": "orig", "mtime": 1_600_000_000},
    )
    assert created.status_code == 200
    note_id = created.json()["note_id"]

    # Pretend the note was edited locally — arming a real divergence.
    sync = db_session.query(SyncState).filter_by(note_id=note_id).first()
    sync.local_mtime = datetime.now(UTC).replace(tzinfo=None)
    db_session.commit()

    resp = client.post(
        "/webhook/obsidian",
        json={"event": "update", "path": "/vault/gated.md", "content": "remote", "mtime": 1_600_000_000},
    )

    assert resp.status_code == 200
    assert resp.json()["conflict"] is False


def test_webhook_conflict_allowed_with_secret(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "s3cr3t")

    created = client.post(
        "/webhook/obsidian?secret=s3cr3t",
        json={"event": "create", "path": "/vault/gated2.md", "content": "orig", "mtime": 1_600_000_000},
    )
    assert created.status_code == 200
    note_id = created.json()["note_id"]

    sync = db_session.query(SyncState).filter_by(note_id=note_id).first()
    sync.local_mtime = datetime.now(UTC).replace(tzinfo=None)
    db_session.commit()

    resp = client.post(
        "/webhook/obsidian?secret=s3cr3t",
        json={"event": "update", "path": "/vault/gated2.md", "content": "remote", "mtime": 1_600_000_000},
    )

    assert resp.status_code == 200
    assert resp.json()["conflict"] is True


def test_webhook_bad_path_rejected(client: TestClient, db_session, monkeypatch, vault):
    """Webhook-supplied paths get the same confinement: no ``.obsidian``,
    no traversal, no non-.md targets."""
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "")
    monkeypatch.setattr(settings, "auth_password", "")

    for bad in (
        f"{vault}/.obsidian/app.json",
        f"{vault}/../../etc/passwd",
        f"{vault}/_joidy/state.md",
        f"{vault}/file.txt",
    ):
        resp = client.post(
            "/webhook/obsidian",
            json={"event": "create", "path": bad, "content": "x"},
        )
        assert resp.status_code == 400, bad


def test_webhook_legit_path_accepted(client: TestClient, db_session, monkeypatch, vault):
    monkeypatch.setattr(settings, "obsidian_webhook_secret", "")
    monkeypatch.setattr(settings, "auth_password", "")
    resp = client.post(
        "/webhook/obsidian",
        json={"event": "create", "path": str(vault / "ok.md"), "content": "x"},
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "created"
