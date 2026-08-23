import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from config import settings
from database import SessionLocal
from models.note import EmbeddingFailure, Note
from services.embedding_retry import compute_retry_delay_seconds
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_EMBEDDING_HEALTH_TTL = 60.0
_embedding_health_cache: tuple[bool, float] | None = None
_embedding_semaphore = asyncio.Semaphore(8)


# ponytail: background tasks need own session; sync callers can pass one
def _session_or_none(db: Session | None) -> Session:
    return db if db is not None else SessionLocal()


async def _embeddings_available() -> bool:
    """Check (cached) whether the ai-service can produce embeddings."""
    if not settings.ai_service_enabled:
        return False
    global _embedding_health_cache
    now = time.monotonic()
    if _embedding_health_cache is not None and now - _embedding_health_cache[1] < _EMBEDDING_HEALTH_TTL:
        return _embedding_health_cache[0]
    available = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ai_service_url}/health")
            if r.status_code == 200:
                body = r.json()
                available = bool((body.get("provider") or {}).get("embedding", {}).get("available"))
    except Exception:
        logger.warning("[embedding] ai-service health check failed, assuming unavailable", exc_info=True)
    _embedding_health_cache = (available, now)
    return available


async def trigger_embedding(
    note_id: int, content: str, db: Session | None = None
) -> None:
    if not await _embeddings_available():
        logger.debug("[embedding] skipped note_id=%s (no embedding provider available)", note_id)
        return
    async with _embedding_semaphore:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {}
                if settings.internal_secret:
                    headers["X-Internal-Secret"] = settings.internal_secret
                response = await client.post(
                    f"{settings.ai_service_url}/embed",
                    json={"note_id": note_id, "content": content},
                    headers=headers,
                )
                response.raise_for_status()
            await asyncio.to_thread(_clear_embedding_failure_sync, note_id, db)
        except Exception as exc:
            logger.exception("Embedding failed for note_id=%s", note_id)
            await asyncio.to_thread(_record_embedding_failure_sync, note_id, str(exc), db)


def _clear_embedding_failure_sync(note_id: int, db: Session | None) -> None:
    _db = _session_or_none(db)
    try:
        clear_embedding_failure(_db, note_id)
    finally:
        if db is None:
            _db.close()


def _record_embedding_failure_sync(note_id: int, error_message: str, db: Session | None) -> None:
    _db = _session_or_none(db)
    try:
        record_embedding_failure(_db, note_id, error_message)
    finally:
        if db is None:
            _db.close()


def record_embedding_failure(db: Session, note_id: int, error_message: str) -> None:
    failure = db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).first()
    if failure is None:
        failure = EmbeddingFailure(note_id=note_id, attempts=0)
        db.add(failure)

    failure.attempts += 1
    failure.last_error = error_message[:2000]

    max_attempts = settings.embedding_retry_max_attempts
    if failure.attempts >= max_attempts:
        # Move to dead letter — won't be retried automatically
        failure.next_retry_at = None
        logger.warning(
            "Embedding for note_id=%s moved to dead letter after %d attempts: %s",
            note_id, failure.attempts, error_message[:200],
        )
    else:
        delay = compute_retry_delay_seconds(failure.attempts, settings.embedding_retry_base_seconds)
        failure.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        logger.info(
            "Embedding retry scheduled for note_id=%s attempt=%d delay=%ds",
            note_id, failure.attempts, delay,
        )
    db.commit()


def clear_embedding_failure(db: Session, note_id: int) -> None:
    db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).delete()
    db.commit()


def get_retryable_embedding_notes(db: Session, limit: int = 20) -> list[Note]:
    """Get notes whose embeddings failed but are still retryable (not dead-lettered)."""
    now = datetime.now(timezone.utc)
    max_attempts = settings.embedding_retry_max_attempts
    failures = (
        db.query(EmbeddingFailure)
        .filter(EmbeddingFailure.attempts < max_attempts)
        .filter((EmbeddingFailure.next_retry_at.is_(None)) | (EmbeddingFailure.next_retry_at <= now))
        .order_by(EmbeddingFailure.updated_at.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )

    notes: list[Note] = []
    for failure in failures:
        note = db.query(Note).filter(Note.id == failure.note_id).first()
        if note is None:
            db.delete(failure)
            continue
        notes.append(note)

    return notes


def get_dead_letter_entries(db: Session, limit: int = 50) -> list[dict]:
    """Get embedding failures that exceeded max retry attempts (dead letter queue)."""
    max_attempts = settings.embedding_retry_max_attempts
    failures = (
        db.query(EmbeddingFailure)
        .filter(EmbeddingFailure.attempts >= max_attempts)
        .order_by(EmbeddingFailure.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "note_id": f.note_id,
            "attempts": f.attempts,
            "last_error": f.last_error[:500],
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in failures
    ]


def reset_dead_letter_entry(db: Session, note_id: int) -> bool:
    """Reset a dead-lettered failure so it can be retried."""
    failure = db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).first()
    if not failure:
        return False
    failure.attempts = 0
    failure.next_retry_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Dead letter entry reset for note_id=%s", note_id)
    return True


def purge_dead_letters(db: Session) -> int:
    """Remove all dead-lettered failures."""
    max_attempts = settings.embedding_retry_max_attempts
    count = db.query(EmbeddingFailure).filter(EmbeddingFailure.attempts >= max_attempts).delete()
    db.commit()
    logger.info("Purged %d dead letter entries", count)
    return count

