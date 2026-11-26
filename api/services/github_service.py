import logging

from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItemType,
    GitHubRepo,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def record_event(
    db: Session,
    repo_id: int,
    event_type: GitHubEventType,
    action: str,
    sender: str,
    payload: dict,
    item_type: GitHubItemType | None = None,
    item_number: int | None = None,
    item_external_id: int | None = None,
) -> GitHubEvent:
    event = GitHubEvent(
        repo_id=repo_id,
        event_type=event_type,
        action=action,
        sender=sender,
        payload=payload,
        item_type=item_type,
        item_number=item_number,
        item_external_id=item_external_id,
    )
    db.add(event)
    db.commit()
    return event


def process_webhook_event(
    db: Session,
    repo_full_name: str,
    event_type: GitHubEventType,
    action: str,
    sender: str,
    payload: dict,
) -> GitHubEvent | None:
    repo = db.execute(select(GitHubRepo).where(GitHubRepo.full_name == repo_full_name)).scalar_one_or_none()
    if not repo:
        logger.warning(f"Repo not found in DB: {repo_full_name}")
        return None

    item_type: GitHubItemType | None = None
    item_number: int | None = None
    item_external_id: int | None = None

    if event_type == GitHubEventType.ISSUES and "issue" in payload:
        issue = payload["issue"]
        item_type = GitHubItemType.ISSUE
        item_number = issue["number"]
        item_external_id = issue["id"]
    elif event_type == GitHubEventType.PULL_REQUEST and "pull_request" in payload:
        pr = payload["pull_request"]
        item_type = GitHubItemType.PR
        item_number = pr["number"]
        item_external_id = pr["id"]

    event = record_event(
        db,
        repo.id,
        event_type,
        action,
        sender,
        payload,
        item_type,
        item_number,
        item_external_id,
    )
    return event
