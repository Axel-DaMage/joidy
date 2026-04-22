import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from models.note import EmbeddingFailure, Note
from services.embedding_retry import compute_retry_delay_seconds


logger = logging.getLogger(__name__)


async def trigger_embedding(note_id: int, content: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ai_service_url}/embed",
                json={"note_id": note_id, "content": content},
            )
            response.raise_for_status()
        clear_embedding_failure(note_id)
    except Exception as exc:
        record_embedding_failure(note_id, str(exc))
        logger.exception("Embedding failed for note_id=%s", note_id)


def record_embedding_failure(note_id: int, error_message: str) -> None:
    with SessionLocal() as db:
        failure = db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).first()
        if failure is None:
            failure = EmbeddingFailure(note_id=note_id, attempts=0)
            db.add(failure)

        failure.attempts += 1
        failure.last_error = error_message[:2000]
        delay = compute_retry_delay_seconds(failure.attempts, settings.embedding_retry_base_seconds)
        failure.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        db.commit()


def clear_embedding_failure(note_id: int) -> None:
    with SessionLocal() as db:
        db.query(EmbeddingFailure).filter(EmbeddingFailure.note_id == note_id).delete()
        db.commit()


def get_retryable_embedding_notes(db: Session, limit: int = 20) -> list[Note]:
    now = datetime.utcnow()
    failures = (
        db.query(EmbeddingFailure)
        .filter(EmbeddingFailure.attempts < settings.embedding_retry_max_attempts)
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
