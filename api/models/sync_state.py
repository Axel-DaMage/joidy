from datetime import datetime

from database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SyncState(Base):
    """Track Obsidian sync state and conflicts per note."""

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    local_mtime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remote_mtime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conflict: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    note: Mapped["Note"] = relationship("Note", backref="sync_state")
