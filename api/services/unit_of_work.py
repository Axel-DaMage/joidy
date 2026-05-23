"""
Unit of Work pattern for database operations.
Provides transactional grouping of multiple operations.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

from database import SessionLocal


class UnitOfWork:
    """
    Unit of Work context manager for transactional database operations.
    Usage:
        with UnitOfWork() as uow:
            uow.notes.create(...)
            uow.tags.create(...)
            # Automatically commits on success, rolls back on exception
    """

    def __init__(self):
        self._session: Session | None = None

    def __enter__(self) -> 'UnitOfWork':
        self._session = SessionLocal()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._session is None:
            return False

        if exc_type is not None:
            self._session.rollback()
            self._session.close()
            return False

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        finally:
            self._session.close()
        return True

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized. Use 'with' context.")
        return self._session

    @property
    def notes(self):
        from services.note_service import NoteService
        return NoteService(self._session)

    @property
    def tags(self):
        from services.tag_service import TagService
        return TagService(self._session)

    @property
    def goals(self):
        from services.goal_service import GoalService
        return GoalService(self._session)

    @property
    def skills(self):
        from services.skill_tree_service import SkillTreeService
        return SkillTreeService(self._session)


@contextmanager
def unit_of_work() -> Generator[UnitOfWork, None, None]:
    """Alternative function-based syntax for Unit of Work."""
    uow = UnitOfWork()
    try:
        yield uow
    except Exception:
        if uow._session:
            uow._session.rollback()
        raise
    finally:
        if uow._session:
            uow._session.close()