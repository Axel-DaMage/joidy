"""
Repository (Data Access) layer for Joidy API.

One repository per domain model, wrapping SQLAlchemy Session with
domain-specific query methods. Injected via FastAPI Depends.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timedelta
from typing import Generic, TypeVar

from fastapi import Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from database import get_db
from models.config import SystemConfig
from models.gamification import StreakRecord, UserStats, XPEvent
from models.github import GitHubEvent, GitHubItem, GitHubRepo
from models.goal import Goal, GoalState
from models.note import (
    EmbeddingFailure,
    Note,
    NoteLink,
    NoteTag,
    Tag,
    TagCooccurrence,
)
from models.personal_streaks import PersonalStreak, StreakCheckIn
from models.planning import PlanningAssignment
from models.skill import Skill

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Generic CRUD base for domain repositories."""

    def __init__(self, db: Session, model: type[ModelT]) -> None:
        self._db = db
        self._model = model

    # ponytail: generic CRUD, add specific queries in subclasses

    def get(self, id: int) -> ModelT | None:
        return self._db.get(self._model, id)

    def list(self, skip: int = 0, limit: int = 100) -> list[ModelT]:
        return self._db.query(self._model).offset(skip).limit(limit).all()

    def add(self, instance: ModelT) -> ModelT:
        self._db.add(instance)
        self._db.flush()
        self._db.refresh(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        self._db.delete(instance)

    def count(self) -> int:
        return self._db.query(self._model).count()


# ─── Note ────────────────────────────────────────────────────────────────────


class NoteRepository(BaseRepository[Note]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Note)

    def find_by_path(self, path: str) -> Note | None:
        return self._db.query(Note).filter(Note.source_path == path).first()

    def find_by_tag(self, tag_id: int) -> list[Note]:
        return (
            self._db.query(Note)
            .join(NoteTag)
            .filter(NoteTag.tag_id == tag_id)
            .all()
        )

    def search(self, query: str, limit: int = 20) -> list[Note]:
        q = f"%{query}%"
        return (
            self._db.query(Note)
            .filter(Note.title.ilike(q) | Note.content.ilike(q))
            .limit(limit)
            .all()
        )

    def get_orphaned(self) -> list[Note]:
        """Notes not linked to any goal or tag."""
        return (
            self._db.query(Note)
            .outerjoin(NoteTag)
            .filter(NoteTag.tag_id.is_(None))
            .all()
        )

    def get_recent(self, days: int = 7) -> list[Note]:
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self._db.query(Note)
            .filter(Note.created_at >= since)
            .order_by(Note.created_at.desc())
            .all()
        )

    def get_created_between(
        self, start: datetime, end: datetime
    ) -> list[Note]:
        return (
            self._db.query(Note)
            .filter(Note.created_at >= start, Note.created_at < end)
            .all()
        )


class TagRepository(BaseRepository[Tag]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Tag)

    def find_by_name(self, name: str) -> Tag | None:
        return self._db.query(Tag).filter(Tag.name == name).first()


class NoteTagRepository(BaseRepository[NoteTag]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, NoteTag)


class NoteLinkRepository(BaseRepository[NoteLink]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, NoteLink)

    def find_by_source(self, source_note_id: int) -> list[NoteLink]:
        return (
            self._db.query(NoteLink)
            .filter(NoteLink.source_note_id == source_note_id)
            .all()
        )

    def delete_for_note(self, note_id: int) -> None:
        self._db.query(NoteLink).filter(
            (NoteLink.source_note_id == note_id)
            | (NoteLink.target_note_id == note_id)
        ).delete()


class TagCooccurrenceRepository(BaseRepository[TagCooccurrence]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, TagCooccurrence)

    def delete_for_tags(self, tag_ids: set[int]) -> None:
        self._db.query(TagCooccurrence).filter(
            (TagCooccurrence.tag_a_id.in_(tag_ids))
            | (TagCooccurrence.tag_b_id.in_(tag_ids))
        ).delete(synchronize_session=False)

    def get_graph_data(self, limit: int = 200) -> list[TagCooccurrence]:
        return (
            self._db.query(TagCooccurrence)
            .order_by(TagCooccurrence.weight.desc())
            .limit(limit)
            .all()
        )


class EmbeddingFailureRepository(BaseRepository[EmbeddingFailure]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, EmbeddingFailure)

    def find_by_note(self, note_id: int) -> EmbeddingFailure | None:
        return (
            self._db.query(EmbeddingFailure)
            .filter(EmbeddingFailure.note_id == note_id)
            .first()
        )

    def get_retryable(self, limit: int = 20) -> list[EmbeddingFailure]:
        now = datetime.utcnow()
        return (
            self._db.query(EmbeddingFailure)
            .filter(
                EmbeddingFailure.next_retry_at.is_(None)
                | (EmbeddingFailure.next_retry_at <= now)
            )
            .limit(limit)
            .all()
        )

    def get_dead_letters(self, limit: int = 50) -> list[EmbeddingFailure]:
        now = datetime.utcnow()
        return (
            self._db.query(EmbeddingFailure)
            .filter(
                EmbeddingFailure.next_retry_at.isnot(None),
                EmbeddingFailure.next_retry_at > now,
            )
            .limit(limit)
            .all()
        )

    def count_dead_letters(self) -> int:
        now = datetime.utcnow()
        return (
            self._db.query(EmbeddingFailure)
            .filter(
                EmbeddingFailure.next_retry_at.isnot(None),
                EmbeddingFailure.next_retry_at > now,
            )
            .count()
        )


# ─── Goal ────────────────────────────────────────────────────────────────────


class GoalRepository(BaseRepository[Goal]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Goal)

    def get_active(self) -> list[Goal]:
        return (
            self._db.query(Goal)
            .filter(Goal.state == GoalState.ACTIVE)
            .all()
        )

    def get_by_note(self, note_id: int) -> list[Goal]:
        return (
            self._db.query(Goal).filter(Goal.note_id == note_id).all()
        )

    def get_failed(self) -> list[Goal]:
        return (
            self._db.query(Goal)
            .filter(Goal.state == GoalState.FAILED)
            .all()
        )

    def get_completed_since(self, since: datetime) -> list[Goal]:
        return (
            self._db.query(Goal)
            .filter(
                Goal.state == GoalState.COMPLETED,
                Goal.completed_at >= since,
            )
            .all()
        )


class PlanningAssignmentRepository(BaseRepository[PlanningAssignment]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, PlanningAssignment)


# ─── Gamification ────────────────────────────────────────────────────────────


class UserStatsRepository(BaseRepository[UserStats]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, UserStats)

    def get_or_create(self) -> UserStats:
        stats = self._db.query(UserStats).first()
        if stats is None:
            stats = UserStats()
            self._db.add(stats)
            self._db.flush()
            self._db.refresh(stats)
        return stats


class XPEventRepository(BaseRepository[XPEvent]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, XPEvent)

    def get_recent(self, limit: int = 50) -> list[XPEvent]:
        return (
            self._db.query(XPEvent)
            .order_by(XPEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_since(self, since: datetime) -> int:
        return (
            self._db.query(XPEvent)
            .filter(XPEvent.created_at >= since)
            .count()
        )


class StreakRecordRepository(BaseRepository[StreakRecord]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, StreakRecord)

    def get_today(self) -> StreakRecord | None:
        return (
            self._db.query(StreakRecord)
            .filter(StreakRecord.activity_date == date.today())
            .first()
        )


# ─── GitHub ──────────────────────────────────────────────────────────────────


class GitHubRepoRepository(BaseRepository[GitHubRepo]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, GitHubRepo)

    def find_by_full_name(self, full_name: str) -> GitHubRepo | None:
        return (
            self._db.query(GitHubRepo)
            .filter(GitHubRepo.full_name == full_name)
            .first()
        )


class GitHubItemRepository(BaseRepository[GitHubItem]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, GitHubItem)

    def find_by_external_id(self, external_id: int) -> GitHubItem | None:
        return (
            self._db.query(GitHubItem)
            .filter(GitHubItem.external_id == external_id)
            .first()
        )

    def list_by_repo(self, repo_id: int) -> list[GitHubItem]:
        return (
            self._db.query(GitHubItem)
            .filter(GitHubItem.repo_id == repo_id)
            .all()
        )


class GitHubEventRepository(BaseRepository[GitHubEvent]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, GitHubEvent)

    def list_by_repo(
        self, repo_id: int, limit: int = 50
    ) -> list[GitHubEvent]:
        return (
            self._db.query(GitHubEvent)
            .filter(GitHubEvent.repo_id == repo_id)
            .order_by(GitHubEvent.created_at.desc())
            .limit(limit)
            .all()
        )


# ─── Skill ───────────────────────────────────────────────────────────────────


class SkillRepository(BaseRepository[Skill]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Skill)

    def find_by_name(self, name: str) -> Skill | None:
        return (
            self._db.query(Skill)
            .join(Skill.tag)
            .filter(Tag.name == name)
            .first()
        )

    def find_roots(self) -> list[Skill]:
        """Skills whose tag has no parent tag."""
        return (
            self._db.query(Skill)
            .join(Skill.tag)
            .filter(Tag.parent_id.is_(None))
            .all()
        )


# ─── Personal Streaks ────────────────────────────────────────────────────────


class PersonalStreakRepository(BaseRepository[PersonalStreak]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, PersonalStreak)

    def get_active(self) -> list[PersonalStreak]:
        return (
            self._db.query(PersonalStreak)
            .filter(PersonalStreak.is_archived.is_(False))
            .all()
        )


class StreakCheckInRepository(BaseRepository[StreakCheckIn]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, StreakCheckIn)


# ─── Config ──────────────────────────────────────────────────────────────────


class ConfigRepository(BaseRepository[SystemConfig]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, SystemConfig)

    def get_all_as_dict(self) -> dict[str, str]:
        rows = self._db.query(SystemConfig).all()
        return {r.key: r.value or "" for r in rows}

    def get(self, key: str) -> str | None:
        row = self._db.query(SystemConfig).filter(SystemConfig.key == key).first()
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self._db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            row.value = value
        else:
            self._db.add(SystemConfig(key=key, value=value))
        self._db.flush()


# ─── FastAPI DI providers ────────────────────────────────────────────────────


def get_note_repo(db: Session = Depends(get_db)) -> NoteRepository:
    return NoteRepository(db)


def get_tag_repo(db: Session = Depends(get_db)) -> TagRepository:
    return TagRepository(db)


def get_note_tag_repo(db: Session = Depends(get_db)) -> NoteTagRepository:
    return NoteTagRepository(db)


def get_note_link_repo(db: Session = Depends(get_db)) -> NoteLinkRepository:
    return NoteLinkRepository(db)


def get_tag_cooccurrence_repo(
    db: Session = Depends(get_db),
) -> TagCooccurrenceRepository:
    return TagCooccurrenceRepository(db)


def get_embedding_failure_repo(
    db: Session = Depends(get_db),
) -> EmbeddingFailureRepository:
    return EmbeddingFailureRepository(db)


def get_goal_repo(db: Session = Depends(get_db)) -> GoalRepository:
    return GoalRepository(db)


def get_planning_assignment_repo(
    db: Session = Depends(get_db),
) -> PlanningAssignmentRepository:
    return PlanningAssignmentRepository(db)


def get_user_stats_repo(db: Session = Depends(get_db)) -> UserStatsRepository:
    return UserStatsRepository(db)


def get_xp_event_repo(db: Session = Depends(get_db)) -> XPEventRepository:
    return XPEventRepository(db)


def get_streak_record_repo(
    db: Session = Depends(get_db),
) -> StreakRecordRepository:
    return StreakRecordRepository(db)


def get_github_repo_repo(
    db: Session = Depends(get_db),
) -> GitHubRepoRepository:
    return GitHubRepoRepository(db)


def get_github_item_repo(
    db: Session = Depends(get_db),
) -> GitHubItemRepository:
    return GitHubItemRepository(db)


def get_github_event_repo(
    db: Session = Depends(get_db),
) -> GitHubEventRepository:
    return GitHubEventRepository(db)


def get_skill_repo(db: Session = Depends(get_db)) -> SkillRepository:
    return SkillRepository(db)


def get_personal_streak_repo(
    db: Session = Depends(get_db),
) -> PersonalStreakRepository:
    return PersonalStreakRepository(db)


def get_streak_checkin_repo(
    db: Session = Depends(get_db),
) -> StreakCheckInRepository:
    return StreakCheckInRepository(db)


def get_config_repo(db: Session = Depends(get_db)) -> ConfigRepository:
    return ConfigRepository(db)