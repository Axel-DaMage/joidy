import os
import re

from config import settings
from models.note import Note, NoteLink, NoteTag, Tag
from services.gamification_engine import (
    GamificationResult,
    process_event,
    xp_for,
)
from services.goal_service import sync_goals_from_note
from services.response_cache import clear_api_caches
from services.sanitizer import sanitize_content, sanitize_tag, sanitize_title
from services.skill_tree import sync_skills, sync_skills_for_tags
from services.tag_graph import (
    rebuild_tag_cooccurrences,
    sync_tag_cooccurrences_for_tags,
)
from services.vault_paths import normalize_source_path, resolve_confined_source_path
from sqlalchemy.orm import Session, selectinload


def rebuild_derived_data(db: Session) -> None:
    """Rebuild the derived tag graph and skill table after bulk note imports."""
    rebuild_tag_cooccurrences(db)
    sync_skills(db)


def write_to_vault(note: Note, from_vault: bool = False) -> bool:
    """Write note content back to the vault file if source_path is set.

    Avoids writing when the update came from the vault watcher (which would
    trigger a feedback loop) and skips no-op writes where the file already
    has the same content.

    Confinement (#1287, #1314): the target is resolved with
    ``resolve_confined_source_path`` — realpath + commonpath against the
    effective vault root, ``.md`` only, and no hidden dirs (``.obsidian`` …)
    or ``_joidy/`` — so prefix confusion (``/vault_evil``) and planted
    symlinks can never redirect the write outside the vault.
    """
    if from_vault:
        return False
    if not note.source_path:
        return False
    if not settings.obsidian_vault_path:
        return False
    try:
        # The vault root itself must already be a real directory — without
        # this guard a misconfigured path would let makedirs() fabricate a
        # vault subtree anywhere on the filesystem.
        if not os.path.isdir(os.path.realpath(settings.obsidian_vault_path)):
            return False
        full_path = resolve_confined_source_path(note.source_path)
        if full_path is None:
            return False
        if os.path.exists(full_path):
            try:
                current = open(full_path, encoding="utf-8").read()
            except Exception:
                current = None
            if current is not None and current == note.content:
                return True
        parent = os.path.dirname(full_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(note.content)
        return True
    except Exception:
        return False


def note_to_response(note: Note) -> dict:
    from sqlalchemy import inspect

    insp = inspect(note)
    content = ""
    if "content" not in insp.unloaded:
        content = note.content

    return {
        "id": note.id,
        "title": note.title,
        "content": content,
        "source": note.source,
        "source_path": note.source_path,
        "tags": [nt.tag.name for nt in note.tags if nt.tag],
        "created_at": note.created_at.isoformat() + "Z",
        "updated_at": note.updated_at.isoformat() + "Z",
    }


def get_or_create_tag(db: Session, name: str) -> Tag:
    # Sanitize at the chokepoint so every tag-creation path (note tags, bulk
    # ops, AI tag acceptance) applies the same normalization (#1322).
    normalized = sanitize_tag(name)
    tag = db.query(Tag).filter(Tag.name == normalized).first()
    if not tag:
        tag = Tag(name=normalized)
        db.add(tag)
        db.flush()
    return tag


def sync_note_links(db: Session, source_note_id: int, content: str) -> None:
    """Parse WikiLinks and update note_links table for a note."""
    db.query(NoteLink).filter(NoteLink.source_note_id == source_note_id).delete()

    links = re.findall(r"\[\[\s*([^\]|]+?)\s*(?:\|[^\]]+)?\]\]", content)
    unique_titles = list({title.strip() for title in links})
    if not unique_titles:
        db.flush()
        return

    # Batch-load all target notes in a single query instead of one per link.
    # Use OR of ilike conditions to avoid N+1 queries.
    from sqlalchemy import or_

    conditions = [Note.title.ilike(t) for t in unique_titles]
    targets = db.query(Note).filter(or_(*conditions)).all()
    for target in targets:
        db.add(NoteLink(source_note_id=source_note_id, target_note_id=target.id))

    db.flush()


def create_note(
    db: Session,
    *,
    title: str,
    content: str,
    tags: list[str],
    source: str,
    source_path: str | None,
    rebuild_derived_data: bool = True,
    from_vault: bool = False,
    sync_goals: bool = True,
):
    title = sanitize_title(title)
    content = sanitize_content(content)
    tags = [sanitize_tag(t) for t in tags if sanitize_tag(t)]
    # Re-map client-side vault domains (host path from .env) onto the effective
    # vault root so writes and watcher dedup (#1099) stay consistent.
    source_path = normalize_source_path(source_path)

    # Idempotent creation by source_path — pressing the daily-note button
    # twice must not create duplicate notes pointing at the same file.
    if source_path:
        existing = db.query(Note).filter(Note.source_path == source_path).first()
        if existing is not None:
            return existing, GamificationResult(
                xp_awarded=0,
                total_xp=0,
                current_streak=0,
                plant_stage=0,
                message="La nota ya existe para este archivo del vault.",
            )

    note = Note(title=title, content=content, source=source, source_path=source_path)
    db.add(note)
    db.flush()
    touched_tag_ids: set[int] = set()

    for tag_name in tags:
        tag = get_or_create_tag(db, tag_name)
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))
        touched_tag_ids.add(tag.id)
        process_event(db, "tag_added")

    event = "note_imported_obsidian" if source == "obsidian" else "note_created"
    gami = process_event(db, event, {"note_id": note.id})

    sync_note_links(db, note.id, content)
    if sync_goals:
        sync_goals_from_note(db, note.id, content)
    if rebuild_derived_data:
        sync_tag_cooccurrences_for_tags(db, touched_tag_ids)

    db.commit()
    db.refresh(note)
    if rebuild_derived_data:
        sync_skills_for_tags(db, touched_tag_ids)
    if source_path and not from_vault:
        write_to_vault(note)
        from services.sync_service import update_local_mtime

        update_local_mtime(db, note.id)
        db.commit()
    clear_api_caches()

    # Broadcast a vault_synced event when the note came from Obsidian so the
    # frontend can distinguish vault syncs from manual creations (#73). Its
    # payload is a strict superset of note_created (same note_id + title plus
    # source_path) and triggers the same frontend refetch + toast, so the
    # generic frame is skipped for vault-sourced notes — halving the
    # per-write fan-out during bulk imports (#1525).
    if source == "obsidian":
        try:
            from routers.websocket import broadcast_vault_synced

            broadcast_vault_synced(note.id, note.title, note.source_path)
        except Exception:  # noqa: S110 — best-effort realtime broadcast; websocket must not fail the write
            pass
    else:
        try:
            from routers.websocket import broadcast_note_created

            broadcast_note_created(note.id, note.title)
        except Exception:  # noqa: S110 — best-effort realtime broadcast; websocket must not fail the write
            pass

    return note, gami


def update_note(
    db: Session,
    note_id: int,
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    source_path: str | None = None,
    source: str | None = None,
    rebuild_derived_data: bool = True,
    from_vault: bool = False,
):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return None, None

    gami = None
    touched_tag_ids: set[int] = set()

    if title is not None:
        note.title = sanitize_title(title)
    if source_path is not None:
        note.source_path = normalize_source_path(source_path)
    if source is not None:
        note.source = source
    if content is not None:
        content = sanitize_content(content)
        old_len = len(note.content)
        note.content = content
        if abs(len(content) - old_len) > 50:
            gami = process_event(db, "note_edited", {"note_id": note.id})
    if tags is not None:
        touched_tag_ids = {tag_id for (tag_id,) in db.query(NoteTag.tag_id).filter(NoteTag.note_id == note_id).all()}
        db.query(NoteTag).filter(NoteTag.note_id == note_id).delete()
        db.flush()
        for tag_name in tags:
            clean_tag = sanitize_tag(tag_name)
            if not clean_tag:
                continue
            tag = get_or_create_tag(db, clean_tag)
            db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="manual"))
            touched_tag_ids.add(tag.id)

    if gami is None:
        gami = process_event(db, "note_edited", {"note_id": note.id})

    if content is not None:
        sync_note_links(db, note.id, content)
        sync_goals_from_note(db, note.id, content)
    if tags is not None:
        if rebuild_derived_data:
            sync_tag_cooccurrences_for_tags(db, touched_tag_ids)

    db.commit()
    db.refresh(note)
    if rebuild_derived_data and touched_tag_ids:
        sync_skills_for_tags(db, touched_tag_ids)
    if content is not None and not from_vault:
        write_to_vault(note)
        from services.sync_service import update_local_mtime

        update_local_mtime(db, note.id)
        db.commit()
    clear_api_caches()

    # Broadcast a vault_synced event when the update came from Obsidian so the
    # frontend can distinguish vault syncs from manual edits (#73). As in
    # create_note, its payload covers note_updated's and drives the same
    # refetch, so the generic frame is only sent for non-vault writes (#1525).
    if from_vault or note.source == "obsidian":
        try:
            from routers.websocket import broadcast_vault_synced

            broadcast_vault_synced(note.id, note.title, note.source_path)
        except Exception:  # noqa: S110 — best-effort realtime broadcast; websocket must not fail the write
            pass
    else:
        try:
            from routers.websocket import broadcast_note_updated

            broadcast_note_updated(note.id, note.title)
        except Exception:  # noqa: S110 — best-effort realtime broadcast; websocket must not fail the write
            pass

    return note, gami


def delete_note(db: Session, note_id: int) -> bool:
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return False

    touched_tag_ids = {nt.tag_id for nt in note.tags}

    # Revert XP awarded for note creation to prevent XP farming
    from models.gamification import UserStats, XPEvent

    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    if stats:
        xp_to_revert = xp_for("note_created", db, 10)
        stats.total_xp = max(0, stats.total_xp - xp_to_revert)
        db.add(XPEvent(event_type="note_deleted", xp=-xp_to_revert, metadata_json=f'{{"note_id": {note_id}}}'))

    db.delete(note)
    sync_tag_cooccurrences_for_tags(db, touched_tag_ids)
    db.commit()
    sync_skills_for_tags(db, touched_tag_ids)
    clear_api_caches()
    return True


def accept_ai_tag(db: Session, note_id: int, tag_name: str):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return None, None

    tag = get_or_create_tag(db, tag_name)
    existing = db.query(NoteTag).filter(NoteTag.note_id == note_id, NoteTag.tag_id == tag.id).first()
    if not existing:
        db.add(NoteTag(note_id=note.id, tag_id=tag.id, source="ai", confidence=0.9))
        sync_tag_cooccurrences_for_tags(db, {tag.id})

    gami = process_event(db, "tag_accepted_ai", {"note_id": note_id, "tag": tag_name})
    db.commit()
    sync_skills_for_tags(db, {tag.id})
    clear_api_caches()
    return tag, gami


def list_backlinks(db: Session, note_id: int) -> list[Note]:
    return (
        db.query(Note)
        .join(NoteLink, NoteLink.source_note_id == Note.id)
        .options(selectinload(Note.tags).selectinload(NoteTag.tag))
        .filter(NoteLink.target_note_id == note_id)
        .all()
    )
