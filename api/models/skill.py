from datetime import datetime

from database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

SKILL_LEVELS = {
    "apprentice": (3, 9),
    "journeyman": (10, 24),
    "expert": (25, 49),
    "master": (50, float("inf")),
}


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), unique=True)
    note_count: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(20), default="locked")  # locked|apprentice|journeyman|expert|master
    xp: Mapped[int] = mapped_column(Integer, default=0)
    first_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tag: Mapped["Tag"] = relationship("Tag")  # type: ignore


def compute_skill_level(note_count: int) -> str:
    if note_count < 3:
        return "locked"
    for level, (low, high) in SKILL_LEVELS.items():
        if low <= note_count <= high:
            return level
    return "master"
