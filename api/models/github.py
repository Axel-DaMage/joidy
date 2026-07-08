from datetime import datetime
from enum import Enum as PyEnum

from database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class GitHubRepoStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


class GitHubItemType(str, PyEnum):
    ISSUE = "ISSUE"
    PR = "PR"
    COMMIT = "COMMIT"


class GitHubSyncStatus(str, PyEnum):
    SYNCED = "SYNCED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class GitHubEventType(str, PyEnum):
    ISSUES = "issues"
    PULL_REQUEST = "pull_request"
    ISSUE_COMMENT = "issue_comment"
    PUSH = "push"


class GitHubRepo(Base):
    __tablename__ = "github_repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[GitHubRepoStatus] = mapped_column(Enum(GitHubRepoStatus), default=GitHubRepoStatus.ACTIVE)
    webhook_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(100), nullable=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class GitHubItem(Base):
    __tablename__ = "github_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("github_repos.id"), nullable=False)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    item_type: Mapped[GitHubItemType] = mapped_column(Enum(GitHubItemType), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(20), default="open")
    state_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    author: Mapped[str] = mapped_column(String(100), default="")
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    labels: Mapped[str] = mapped_column(String(500), default="")

    url: Mapped[str] = mapped_column(String(500), nullable=False)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)

    goal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("goals.id"), nullable=True)
    note_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("notes.id"), nullable=True)

    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    repo: Mapped["GitHubRepo"] = relationship("GitHubRepo")  # type: ignore
    goal: Mapped["Goal | None"] = relationship("Goal")  # type: ignore


class GitHubEvent(Base):
    __tablename__ = "github_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("github_repos.id"), nullable=False)

    event_type: Mapped[GitHubEventType] = mapped_column(Enum(GitHubEventType), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    sender: Mapped[str] = mapped_column(String(100), nullable=False)

    item_type: Mapped[GitHubItemType | None] = mapped_column(Enum(GitHubItemType), nullable=True)
    item_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_external_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    repo: Mapped["GitHubRepo"] = relationship("GitHubRepo")  # type: ignore
