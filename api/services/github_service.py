import logging
import secrets
from typing import Any

import httpx
from config import settings
from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItem,
    GitHubItemType,
    GitHubRepo,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    if not settings.github_token:
        raise ValueError("GitHub token not configured")
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def fetch_github(url: str, params: dict | None = None) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{GITHUB_API}{url}", headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


async def post_github(url: str, data: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{GITHUB_API}{url}", headers=_headers(), json=data)
        r.raise_for_status()
        return r.json()


async def patch_github(url: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.patch(f"{GITHUB_API}{url}", headers=_headers(), json=data)
        r.raise_for_status()
        return r.json()


async def delete_github(url: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(f"{GITHUB_API}{url}", headers=_headers())
        r.raise_for_status()


async def get_user() -> dict:
    return await fetch_github("/user")


async def get_repos() -> list[dict]:
    return await fetch_github("/user/repos", {"per_page": 100, "sort": "updated"})


async def get_repo(owner: str, repo: str) -> dict:
    return await fetch_github(f"/repos/{owner}/{repo}")


async def get_issues(owner: str, repo: str, state: str = "open") -> list[dict]:
    return await fetch_github(
        f"/repos/{owner}/{repo}/issues", {"state": state, "per_page": 100, "sort": "updated"}
    )


async def get_pulls(owner: str, repo: str, state: str = "open") -> list[dict]:
    return await fetch_github(
        f"/repos/{owner}/{repo}/pulls", {"state": state, "per_page": 100, "sort": "updated"}
    )


async def get_issue(owner: str, repo: str, issue_number: int) -> dict:
    return await fetch_github(f"/repos/{owner}/{repo}/issues/{issue_number}")


async def get_pull(owner: str, repo: str, pull_number: int) -> dict:
    return await fetch_github(f"/repos/{owner}/{repo}/pulls/{pull_number}")


async def create_issue(
    owner: str, repo: str, title: str, body: str = "", labels: list[str] | None = None
) -> dict:
    data: dict[str, Any] = {"title": title}
    if body:
        data["body"] = body
    if labels:
        data["labels"] = labels
    return await post_github(f"/repos/{owner}/{repo}/issues", data)


async def update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    labels: list[str] | None = None,
) -> dict:
    data: dict[str, Any] = {}
    if title is not None:
        data["title"] = title
    if body is not None:
        data["body"] = body
    if state is not None:
        data["state"] = state
    if labels is not None:
        data["labels"] = labels
    return await patch_github(f"/repos/{owner}/{repo}/issues/{issue_number}", data)


async def close_issue(owner: str, repo: str, issue_number: int) -> dict:
    return await update_issue(owner, repo, issue_number, state="closed")


async def get_comments(owner: str, repo: str, issue_number: int) -> list[dict]:
    return await fetch_github(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")


async def create_comment(owner: str, repo: str, issue_number: int, body: str) -> dict:
    return await post_github(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {"body": body})


async def create_webhook(
    owner: str, repo: str, callback_url: str, secret: str
) -> dict:
    hook_config = {
        "url": callback_url,
        "content_type": "json",
        "secret": secret,
    }
    events = ["issues", "pull_request", "issue_comment", "push"]
    data = {
        "config": hook_config,
        "events": events,
        "active": True,
    }
    return await post_github(f"/repos/{owner}/{repo}/hooks", data)


async def delete_webhook(owner: str, repo: str, hook_id: int) -> None:
    await delete_github(f"/repos/{owner}/{repo}/hooks/{hook_id}")


async def get_commits(owner: str, repo: str, per_page: int = 30) -> list[dict]:
    return await fetch_github(
        f"/repos/{owner}/{repo}/commits", {"per_page": per_page, "sha": "HEAD"}
    )


async def get_file_content(owner: str, repo: str, path: str) -> dict:
    return await fetch_github(f"/repos/{owner}/{repo}/contents/{path}")


def create_repo_in_db(db: Session, full_name: str, description: str | None = None) -> GitHubRepo:
    parts = full_name.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid repo full_name: {full_name}")
    owner, name = parts
    repo_data = {"name": name, "full_name": full_name, "description": description}
    return db.execute(
        select(GitHubRepo).where(GitHubRepo.full_name == full_name)
    ).scalar_one_or_none() or GitHubRepo(**repo_data)


def sync_repos_to_db(db: Session) -> list[GitHubRepo]:
    pass


def sync_issues_to_db(db: Session, repo_id: int, repo_full_name: str) -> list[GitHubItem]:
    pass


def link_goal_to_issue(db: Session, goal_id: int, item_id: int) -> GitHubItem | None:
    item = db.get(GitHubItem, item_id)
    if item:
        item.goal_id = goal_id
        db.commit()
    return item


def unlink_goal_from_issue(db: Session, item_id: int) -> GitHubItem | None:
    item = db.get(GitHubItem, item_id)
    if item:
        item.goal_id = None
        db.commit()
    return item


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
    repo = (
        db.execute(select(GitHubRepo).where(GitHubRepo.full_name == repo_full_name))
        .scalar_one_or_none()
    )
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


def get_webhook_secret() -> str:
    return secrets.token_hex(32)


async def setup_repo_webhook(
    db: Session,
    repo_full_name: str,
    webhook_callback_url: str,
) -> dict | None:
    parts = repo_full_name.split("/")
    if len(parts) != 2:
        return None
    owner, name = parts

    secret = get_webhook_secret()
    webhook = await create_webhook(owner, name, webhook_callback_url, secret)

    repo = (
        db.execute(select(GitHubRepo).where(GitHubRepo.full_name == repo_full_name))
        .scalar_one_or_none()
    )
    if repo:
        repo.webhook_id = webhook["id"]
        repo.webhook_secret = secret
        db.commit()

    return webhook


def get_items_by_goal(db: Session, goal_id: int) -> list[GitHubItem]:
    return list(
        db.execute(
            select(GitHubItem).where(GitHubItem.goal_id == goal_id)
        ).scalars().all()
    )


def get_items_by_repo(db: Session, repo_id: int) -> list[GitHubItem]:
    return list(
        db.execute(select(GitHubItem).where(GitHubItem.repo_id == repo_id)).scalars().all()
    )
