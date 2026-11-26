"""
Repository (Data Access) layer for Joidy API.

One repository per domain model, wrapping SQLAlchemy Session with
domain-specific query methods. Instantiated directly by services and
routers — there is no FastAPI Depends wiring for these (#1528).
"""

from __future__ import annotations

from models.config import SystemConfig
from models.gamification import StreakRecord, UserStats, XPEvent
from models.github import GitHubItem, GitHubRepo
from models.goal import Goal, GoalState
from models.personal_streaks import StreakCheckIn
from models.skill import Skill
from services.timezone_utils import get_local_today
from sqlalchemy.orm import Session


class BaseRepository[ModelT]:
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


# ─── Goal ────────────────────────────────────────────────────────────────────


class GoalRepository(BaseRepository[Goal]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Goal)

    def get_active(self) -> list[Goal]:
        return self._db.query(Goal).filter(Goal.state == GoalState.ACTIVE).all()

    def get_by_note(self, note_id: int) -> list[Goal]:
        return self._db.query(Goal).filter(Goal.note_id == note_id).all()


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

    def find_by_dedup_key(self, event_type: str, dedup_key: str) -> XPEvent | None:
        """Indexed lookup used by XP idempotency guards (#1320)."""
        return self._db.query(XPEvent).filter(XPEvent.event_type == event_type, XPEvent.dedup_key == dedup_key).first()


class StreakRecordRepository(BaseRepository[StreakRecord]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, StreakRecord)

    def get_today(self) -> StreakRecord | None:
        today = get_local_today()
        return self._db.query(StreakRecord).filter(StreakRecord.activity_date == today).first()


# ─── GitHub ──────────────────────────────────────────────────────────────────


class GitHubRepoRepository(BaseRepository[GitHubRepo]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, GitHubRepo)

    def find_by_full_name(self, full_name: str) -> GitHubRepo | None:
        return self._db.query(GitHubRepo).filter(GitHubRepo.full_name == full_name).first()


class GitHubItemRepository(BaseRepository[GitHubItem]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, GitHubItem)


# ─── Skill ───────────────────────────────────────────────────────────────────


class SkillRepository(BaseRepository[Skill]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Skill)

    def list_by_tag_ids(self, tag_ids: set[int]) -> list[Skill]:
        """Skills for the provided tag ids (used by skill-tree sync)."""
        return self._db.query(Skill).filter(Skill.tag_id.in_(tag_ids)).all()


# ─── Personal Streaks ────────────────────────────────────────────────────────


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
