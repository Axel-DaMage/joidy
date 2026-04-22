from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(50), default="joidy")  # joidy | obsidian
    source_path: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tags: Mapped[list["NoteTag"]] = relationship("NoteTag", back_populates="note", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tags.id"), nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#888888")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    notes: Mapped[list["NoteTag"]] = relationship("NoteTag", back_populates="tag", cascade="all, delete-orphan")
    children: Mapped[list["Tag"]] = relationship("Tag", back_populates="parent")
    parent: Mapped["Tag | None"] = relationship("Tag", back_populates="children", remote_side="Tag.id")


class NoteTag(Base):
    __tablename__ = "note_tags"

    note_id: Mapped[int] = mapped_column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    confidence: Mapped[float] = mapped_column(default=1.0)  # 1.0 = manual, <1.0 = AI suggested
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ai

    note: Mapped["Note"] = relationship("Note", back_populates="tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="notes")


class NoteLink(Base):
    """Stores connections between notes (WikiLinks)."""
    __tablename__ = "note_links"

    source_note_id: Mapped[int] = mapped_column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    target_note_id: Mapped[int] = mapped_column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    
    # Optional: context where the link was found
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_note: Mapped["Note"] = relationship("Note", foreign_keys=[source_note_id], backref="out_links")
    target_note: Mapped["Note"] = relationship("Note", foreign_keys=[target_note_id], backref="in_links")


class TagCooccurrence(Base):
    __tablename__ = "tag_cooccurrences"

    tag_a_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    tag_b_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class EmbeddingFailure(Base):
    __tablename__ = "embedding_failures"

    note_id: Mapped[int] = mapped_column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
