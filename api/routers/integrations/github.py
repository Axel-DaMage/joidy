import asyncio
from datetime import datetime
from typing import Any

import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItem,
    GitHubItemType,
    GitHubRepo,
)
from pydantic import BaseModel, Field
from services import github_service as gh_svc
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/integrations/github", tags=["integrations"])

GITHUB_API = "https://api.github.com"


class GitHubRepoCreate(BaseModel):
    full_name: str = Field(..., description="Owner/repo format")
    auto_sync: bool = Field(default=False, description="Enable auto-sync for this repo")


class GitHubIssueCreate(BaseModel):
    repo_full_name: str = Field(..., description="Owner/repo format")
    title: str = Field(..., min_length=1, max_length=500)
    body: str = Field(default="")
    labels: list[str] = Field(default_factory=list)


class GitHubIssueUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    state: str | None = None
    labels: list[str] | None = None


class GitHubGoalLink(BaseModel):
    goal_id: int = Field(..., description="Goal ID to link")


def _headers() -> dict[str, str]:
    if not settings.github_token:
        raise HTTPException(status_code=400, detail="GitHub token not configured")
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _fetch(url: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{GITHUB_API}{url}", headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


async def _post(url: str, data: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{GITHUB_API}{url}", headers=_headers(), json=data)
        r.raise_for_status()
        return r.json()


async def _patch(url: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.patch(f"{GITHUB_API}{url}", headers=_headers(), json=data)
        r.raise_for_status()
        return r.json()


async def _delete(url: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(f"{GITHUB_API}{url}", headers=_headers())
        r.raise_for_status()


@router.get("/status")
async def github_status():
    if not settings.github_token:
        return {"connected": False, "username": None}
    try:
        user = await _fetch("/user")
        return {"connected": True, "username": user.get("login")}
    except Exception:
        return {"connected": False, "username": None}


@router.get("/user")
async def get_current_user():
    return await _fetch("/user")


@router.get("/repos")
async def list_repos(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    sort: str = Query("updated"),
):
    repos = await _fetch(
        "/user/repos", {"page": page, "per_page": per_page, "sort": sort}
    )
    return {
        "repos": [
            {
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description"),
                "private": r.get("private", False),
                "url": r["html_url"],
                "default_branch": r.get("default_branch", "main"),
                "updated_at": r["updated_at"],
            }
            for r in repos
        ]
    }


@router.get("/repos/{owner}/{repo}")
async def get_repo(owner: str, repo: str):
    return await _fetch(f"/repos/{owner}/{repo}")


@router.post("/repos/db")
async def add_repo_to_db(
    db: Session = Depends(get_db),
    full_name: str = Query(..., description="owner/repo"),
):
    parts = full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid format. Use owner/repo")
    owner, name = parts

    try:
        gh_repo = await _fetch(f"/repos/{owner}/{name}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Repo not found: {e}")

    existing = (
        db.execute(select(GitHubRepo).where(GitHubRepo.full_name == full_name))
        .scalar_one_or_none()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Repo already tracked")

    repo = GitHubRepo(
        name=name,
        full_name=gh_repo["full_name"],
        description=gh_repo.get("description"),
        url=gh_repo["html_url"],
        default_branch=gh_repo.get("default_branch", "main"),
        is_private=gh_repo.get("private", False),
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    return {"id": repo.id, "full_name": repo.full_name, "status": repo.status.value}


@router.get("/repos/db")
async def list_repos_in_db(db: Session = Depends(get_db)):
    repos = db.execute(select(GitHubRepo)).scalars().all()
    return {
        "repos": [
            {
                "id": r.id,
                "name": r.name,
                "full_name": r.full_name,
                "status": r.status.value,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
            }
            for r in repos
        ]
    }


@router.delete("/repos/db/{repo_id}")
async def remove_repo_from_db(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(GitHubRepo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    db.execute(
        select(GitHubItem).where(GitHubItem.repo_id == repo_id)
    )
    items = db.execute(select(GitHubItem).where(GitHubItem.repo_id == repo_id)).scalars().all()
    for item in items:
        db.delete(item)

    db.delete(repo)
    db.commit()

    return {"status": "deleted", "repo_id": repo_id}


@router.get("/issues")
async def get_my_issues(
    state: str = Query("open", regex="^(open|closed|all)$"),
    per_page: int = Query(30, le=100),
    filter: str = Query("created", regex="^(all|created|assigned)$"),
):
    try:
        user = await _fetch("/user")
        username = user.get("login", "")

        repos = await _fetch("/user/repos", {"per_page": 30, "sort": "updated"})

        async def fetch_issues_for_repo(repo: dict) -> list:
            try:
                query_state = "all" if filter in ["created", "assigned"] else state
                params = {"state": query_state, "per_page": 50, "sort": "updated"}
                if filter == "created":
                    params["creator"] = username
                elif filter == "assigned":
                    params["assignee"] = username

                issues = await _fetch(f"/repos/{repo['full_name']}/issues", params)
                for i in issues:
                    if "/pull/" in i.get("html_url", ""):
                        continue
                    i["_repo_full_name"] = repo["full_name"]
                return issues
            except Exception as e:
                print(f"Error fetching issues for {repo.get('full_name')}: {e}")
                return []

        results = await asyncio.gather(*[fetch_issues_for_repo(repo) for repo in repos[:15]], return_exceptions=True)
        all_issues = []
        for r in results:
            if isinstance(r, Exception):
                continue
            for i in r:
                if "/pull/" not in i.get("html_url", ""):
                    all_issues.append(i)

        if filter == "all":
            filtered_by_user = [i for i in all_issues if i.get("user", {}).get("login") == username]
            if len(filtered_by_user) > 0:
                all_issues = filtered_by_user

        all_issues.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "issues": [
                {
                    "id": i["id"],
                    "number": i["number"],
                    "title": i["title"],
                    "repo": i.get("_repo_full_name", ""),
                    "url": i["html_url"],
                    "state": i["state"],
                    "labels": [l["name"] for l in i.get("labels", [])],
                    "author": i.get("user", {}).get("login", ""),
                    "created_at": i["created_at"],
                    "updated_at": i["updated_at"],
                }
                for i in all_issues[:per_page]
            ],
            "stats": {
                "total": len(all_issues),
                "open": len([i for i in all_issues if i.get("state") == "open"]),
                "closed": len([i for i in all_issues if i.get("state") == "closed"]),
            },
            "filter": filter,
        }
    except Exception as e:
        print(f"Error in get_my_issues: {e}")
        return {
            "issues": [],
            "stats": {"total": 0, "open": 0, "closed": 0},
            "filter": filter,
        }


@router.get("/pulls")
async def get_my_pulls(
    state: str = Query("open", regex="^(open|closed|all)$"),
    per_page: int = Query(30, le=100),
    filter: str = Query("created", regex="^(all|created|assigned)$"),
):
    try:
        user = await _fetch("/user")
        username = user.get("login", "")

        repos = await _fetch("/user/repos", {"per_page": 30, "sort": "updated"})

        async def fetch_pulls_for_repo(repo: dict) -> list:
            if not repo.get("permissions", {}).get("pull", False):
                return []
            try:
                query_state = "all" if filter in ["created", "assigned"] else state
                params = {"state": query_state, "per_page": 50}
                if filter == "created":
                    params["creator"] = username
                elif filter == "assigned":
                    params["assignee"] = username

                pulls = await _fetch(f"/repos/{repo['full_name']}/pulls", params)
                for p in pulls:
                    p["_repo_full_name"] = repo["full_name"]
                return pulls
            except Exception as e:
                print(f"Error fetching pulls for {repo.get('full_name')}: {e}")
                return []

        results = await asyncio.gather(*[fetch_pulls_for_repo(repo) for repo in repos[:15]], return_exceptions=True)
        all_pulls = []
        for r in results:
            if isinstance(r, Exception):
                continue
            all_pulls.extend(r)

        if filter == "all":
            filtered_by_user = [p for p in all_pulls if p.get("user", {}).get("login") == username]
            if len(filtered_by_user) > 0:
                all_pulls = filtered_by_user

        all_pulls.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {
            "pulls": [
                {
                    "id": p["id"],
                    "number": p["number"],
                    "title": p["title"],
                    "repo": p.get("_repo_full_name", ""),
                    "url": p["html_url"],
                    "state": p["state"],
                    "draft": p.get("draft", False),
                    "author": p.get("user", {}).get("login", ""),
                    "created_at": p.get("created_at"),
                    "updated_at": p["updated_at"],
                }
                for p in all_pulls[:per_page]
            ],
        "stats": {
            "total": len(all_pulls),
            "open": len([p for p in all_pulls if p.get("state") == "open"]),
            "closed": len([p for p in all_pulls if p.get("state") == "closed"]),
            "draft": len([p for p in all_pulls if p.get("draft", False)]),
        },
        "filter": filter,
        }
    except Exception as e:
        print(f"Error in get_my_pulls: {e}")
        return {
            "pulls": [],
            "stats": {"total": 0, "open": 0, "closed": 0, "draft": 0},
            "filter": filter,
        }


@router.get("/repos/{owner}/{repo}/issues")
async def get_repo_issues(
    owner: str,
    repo: str,
    state: str = Query("open", regex="^(open|closed|all)$"),
    per_page: int = Query(30, le=100),
):
    issues = await _fetch(
        f"/repos/{owner}/{repo}/issues",
        {"state": state, "per_page": per_page, "sort": "updated"},
    )
    return {
        "issues": [
            {
                "id": i["id"],
                "number": i["number"],
                "title": i["title"],
                "body": i.get("body", ""),
                "state": i["state"],
                "url": i["html_url"],
                "labels": [l["name"] for l in i.get("labels", [])],
                "author": i.get("user", {}).get("login", ""),
                "assignee": (
                    i.get("assignee", {}).get("login") if i.get("assignee") else None
                ),
                "created_at": i["created_at"],
                "updated_at": i["updated_at"],
            }
            for i in issues
        ]
    }


@router.get("/repos/{owner}/{repo}/issues/{issue_number}")
async def get_issue(owner: str, repo: str, issue_number: int):
    issue = await _fetch(f"/repos/{owner}/{repo}/issues/{issue_number}")
    return {
        "id": issue["id"],
        "number": issue["number"],
        "title": issue["title"],
        "body": issue.get("body", ""),
        "state": issue["state"],
        "url": issue["html_url"],
        "labels": [l["name"] for l in issue.get("labels", [])],
        "author": issue.get("user", {}).get("login", ""),
        "assignee": (
            issue.get("assignee", {}).get("login") if issue.get("assignee") else None
        ),
        "created_at": issue["created_at"],
        "updated_at": issue["updated_at"],
    }


@router.post("/repos/{owner}/{repo}/issues")
async def create_issue(
    owner: str,
    repo: str,
    title: str = Query(..., min_length=1, max_length=500),
    body: str = Query(""),
    labels: list[str] = Query(default_factory=list),
):
    data: dict[str, Any] = {"title": title}
    if body:
        data["body"] = body
    if labels:
        data["labels"] = labels

    issue = await _post(f"/repos/{owner}/{repo}/issues", data)
    return {
        "id": issue["id"],
        "number": issue["number"],
        "title": issue["title"],
        "url": issue["html_url"],
        "state": issue["state"],
    }


@router.patch("/repos/{owner}/{repo}/issues/{issue_number}")
async def update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    title: str | None = Query(None),
    body: str | None = Query(None),
    state: str | None = Query(None, regex="^(open|closed)$"),
    labels: list[str] | None = Query(None),
):
    data: dict[str, Any] = {}
    if title is not None:
        data["title"] = title
    if body is not None:
        data["body"] = body
    if state is not None:
        data["state"] = state
    if labels is not None:
        data["labels"] = labels

    issue = await _patch(f"/repos/{owner}/{repo}/issues/{issue_number}", data)
    return {
        "id": issue["id"],
        "number": issue["number"],
        "title": issue["title"],
        "state": issue["state"],
    }


@router.post("/repos/{owner}/{repo}/issues/{issue_number}/close")
async def close_issue(owner: str, repo: str, issue_number: int):
    issue = await _patch(f"/repos/{owner}/{repo}/issues/{issue_number}", {"state": "closed"})
    return {"number": issue["number"], "state": issue["state"]}


@router.get("/repos/{owner}/{repo}/issues/{issue_number}/comments")
async def get_comments(owner: str, repo: str, issue_number: int):
    comments = await _fetch(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")
    return {
        "comments": [
            {
                "id": c["id"],
                "body": c["body"],
                "author": c["user"]["login"],
                "created_at": c["created_at"],
            }
            for c in comments
        ]
    }


@router.post("/repos/{owner}/{repo}/issues/{issue_number}/comments")
async def add_comment(
    owner: str, repo: str, issue_number: int, body: str = Query(..., min_length=1)
):
    comment = await _post(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {"body": body})
    return {"id": comment["id"], "body": comment["body"]}


@router.get("/repos/{owner}/{repo}/pulls")
async def get_pulls(
    owner: str,
    repo: str,
    state: str = Query("open", regex="^(open|closed|all)$"),
    per_page: int = Query(30, le=100),
):
    pulls = await _fetch(
        f"/repos/{owner}/{repo}/pulls",
        {"state": state, "per_page": per_page, "sort": "updated"},
    )
    return {
        "pulls": [
            {
                "id": p["id"],
                "number": p["number"],
                "title": p["title"],
                "state": p["state"],
                "url": p["html_url"],
                "author": p["user"]["login"],
                "draft": p.get("draft", False),
                "created_at": p["created_at"],
                "updated_at": p["updated_at"],
            }
            for p in pulls
        ]
    }


@router.get("/repos/{owner}/{repo}/commits")
async def get_commits(
    owner: str,
    repo: str,
    per_page: int = Query(30, le=100),
    sha: str | None = Query(None),
):
    params: dict[str, Any] = {"per_page": per_page}
    if sha:
        params["sha"] = sha

    commits = await _fetch(f"/repos/{owner}/{repo}/commits", params)
    return {
        "commits": [
            {
                "sha": c["sha"],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
                "url": c["html_url"],
            }
            for c in commits
        ]
    }


@router.get("/db/items")
async def get_items_in_db(
    db: Session = Depends(get_db),
    repo_id: int | None = Query(None),
    goal_id: int | None = Query(None),
):
    query = select(GitHubItem)
    if repo_id:
        query = query.where(GitHubItem.repo_id == repo_id)
    if goal_id:
        query = query.where(GitHubItem.goal_id == goal_id)

    items = db.execute(query).scalars().all()
    return {
        "items": [
            {
                "id": i.id,
                "repo_id": i.repo_id,
                "external_id": i.external_id,
                "item_type": i.item_type.value,
                "number": i.number,
                "title": i.title,
                "state": i.state,
                "goal_id": i.goal_id,
                "url": i.html_url,
            }
            for i in items
        ]
    }


@router.post("/db/items/{item_id}/link-goal")
async def link_goal(
    item_id: int,
    goal_id: int = Query(...),
    db: Session = Depends(get_db),
):
    item = db.get(GitHubItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in DB")

    item.goal_id = goal_id
    db.commit()

    return {"item_id": item.id, "goal_id": item.goal_id}


@router.delete("/db/items/{item_id}/link-goal")
async def unlink_goal(item_id: int, db: Session = Depends(get_db)):
    item = db.get(GitHubItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in DB")

    item.goal_id = None
    db.commit()

    return {"item_id": item.id, "goal_id": None}


@router.get("/db/events")
async def get_events(
    db: Session = Depends(get_db),
    repo_id: int | None = Query(None),
    limit: int = Query(50, le=100),
):
    query = select(GitHubEvent).order_by(GitHubEvent.created_at.desc()).limit(limit)
    if repo_id:
        query = query.where(GitHubEvent.repo_id == repo_id)

    events = db.execute(query).scalars().all()
    return {
        "events": [
            {
                "id": e.id,
                "repo_id": e.repo_id,
                "event_type": e.event_type.value,
                "action": e.action,
                "sender": e.sender,
                "item_number": e.item_number,
                "processed": e.processed,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }


@router.post("/webhook")
async def receive_webhook(
    db: Session = Depends(get_db),
    x_github_event: str | None = None,
    payload: dict | None = None,
):
    """
    Receive webhook events from GitHub.
    This endpoint should be called by GitHub via webhook configuration.
    """
    event_type = x_github_event or "unknown"
    action = payload.get("action", "") if payload else ""

    repo_full_name = ""
    sender = ""

    if payload:
        if "repository" in payload:
            repo_full_name = payload["repository"].get("full_name", "")
        if "sender" in payload:
            sender = payload["sender"].get("login", "")

    try:
        gh_event_type = GitHubEventType(event_type)
    except ValueError:
        gh_event_type = GitHubEventType.ISSUES

    event = gh_svc.process_webhook_event(
        db, repo_full_name, gh_event_type, action, sender, payload or {}
    )

    return {"status": "received", "event_id": event.id if event else None}


@router.post("/sync/repo/{repo_id}")
async def sync_repo(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(GitHubRepo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    parts = repo.full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid repo full_name")
    owner, name = parts

    try:
        gh_issues = await _fetch(f"/repos/{owner}/{name}/issues", {"state": "all", "per_page": 100})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")

    synced_count = 0
    for issue_data in gh_issues:
        external_id = issue_data["id"]
        existing = (
            db.execute(
                select(GitHubItem).where(
                    GitHubItem.repo_id == repo_id, GitHubItem.external_id == external_id
                )
            )
            .scalar_one_or_none()
        )

        labels_str = ",".join([l["name"] for l in issue_data.get("labels", [])])

        if existing:
            existing.title = issue_data.get("title", "")
            existing.body = issue_data.get("body", "")
            existing.state = issue_data.get("state", "open")
            existing.labels = labels_str
            existing.updated_at = datetime.utcnow()
        else:
            item = GitHubItem(
                repo_id=repo_id,
                external_id=external_id,
                item_type=GitHubItemType.ISSUE,
                number=issue_data["number"],
                title=issue_data.get("title", ""),
                body=issue_data.get("body", ""),
                state=issue_data.get("state", "open"),
                author=issue_data.get("user", {}).get("login", ""),
                assignee=(
                    issue_data.get("assignee", {}).get("login")
                    if issue_data.get("assignee")
                    else None
                ),
                labels=labels_str,
                url=issue_data.get("url", ""),
                html_url=issue_data.get("html_url", ""),
                synced_at=datetime.utcnow(),
            )
            db.add(item)
        synced_count += 1

    repo.last_synced_at = datetime.utcnow()
    db.commit()

    return {
        "repo_id": repo_id,
        "synced": synced_count,
        "last_synced_at": repo.last_synced_at.isoformat(),
    }


GITHUB_OAUTH_SCOPES = [
    "repo",
    "repo:status",
    "repo_deployment",
    "public_repo",
    "repo:invite",
    "security_events",
    "read:user",
    "user:email",
    "user:follow",
    "delete_repo",
    "write:discussion",
    "read:discussion",
    "admin:repo_hook",
    "write:repo_hook",
    "read:repo_hook",
    "admin:org",
    "write:org",
    "read:org",
    "admin:public_key",
    "write:public_key",
    "read:public_key",
    "admin:org_hook",
    "write:org_hook",
    "read:org_hook",
    "workflow",
]


@router.get("/oauth/device/start")
async def start_device_flow():
    """
    Inicia elDevice Flow de OAuth para GitHub.
    Retorna el device_code y user_code para que el usuario autorice.
    """
    if not settings.github_client_id:
        raise HTTPException(
            status_code=400,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID in .env"
        )

    device_auth_url = "https://github.com/login/device/code"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            device_auth_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "client_id": settings.github_client_id,
                "scope": " ".join(GITHUB_OAUTH_SCOPES),
            },
        )
        r.raise_for_status()
        data = r.json()

    return {
        "device_code": data.get("device_code"),
        "user_code": data.get("user_code"),
        "verification_uri": data.get("verification_uri"),
        "verification_uri_secondary": data.get("verification_uri_secondary"),
        "expires_in": data.get("expires_in"),
        "interval": data.get("interval"),
    }


@router.post("/oauth/device/polling")
async def poll_device_code(
    device_code: str = Query(..., description="Device code from start endpoint"),
):
    """
    Hace polling del device_code para obtener el token de acceso.
    Usuario debe autorizar en otro dispositivo first.
    """
    if not settings.github_client_id:
        raise HTTPException(
            status_code=400,
            detail="GitHub OAuth not configured"
        )

    token_url = "https://github.com/login/oauth/access_token"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            token_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        r.raise_for_status()
        data = r.json()

    error = data.get("error")
    if error == "authorization_pending":
        return {"status": "pending", "message": "User has not authorized yet"}
    elif error == "slowdown":
        return {"status": "slowdown", "message": "Wait longer between requests"}
    elif error == "expired_token":
        return {"status": "expired", "message": "Device code expired. Start new flow"}
    elif error == "access_denied":
        return {"status": "denied", "message": "User denied access"}

    access_token = data.get("access_token")
    token_type = data.get("token_type", "bearer")
    scope = data.get("scope", "")

    return {
        "status": "authorized",
        "access_token": access_token,
        "token_type": token_type,
        "scope": scope,
    }


@router.post("/oauth/revoke")
async def revoke_token(
    token: str = Query(..., description="Token to revoke"),
):
    """
    Revoca un token de acceso GitHub.
    """
    revoke_url = "https://github.com/login/oauth/revoke"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            revoke_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "access_token": token,
            },
        )
        r.raise_for_status()

    return {"status": "revoked"}


@router.get("/oauth/scpies")
async def list_oauth_scopes():
    """
    Lista los scopes disponibles para OAuth.
    """
    return {"scopes": GITHUB_OAUTH_SCOPES}


# Paletas de colores para repos (tema oscuro = colores claros, tema claro = colores oscuros)
REPO_PALETTES = [
    ["#7C3AED", "#A78BFA", "#C4B5FD"],  # Violeta
    ["#0EA5E9", "#38BDF8", "#7DD3FC"],  # Cyan
    ["#F59E0B", "#FBBF24", "#FCD34D"],  # Amber
    ["#10B981", "#34D399", "#6EE7B7"],  # Emerald
    ["#EF4444", "#F87171", "#FCA5A5"],  # Red
    ["#EC4899", "#F472B6", "#F9A8D4"],  # Pink
    ["#8B5CF6", "#A78BFA", "#C4B5FD"],  # Purple
    ["#06B6D4", "#22D3EE", "#67E8F9"],  # Teal
    ["#F97316", "#FB923C", "#FDBA74"],  # Orange
    ["#6366F1", "#818CF8", "#A5B4FC"], # Indigo
]


def get_repo_color(repo_name: str, is_dark: bool = True) -> str:
    """Genera un color consistente para un repo basado en su nombre."""
    hash_val = sum(ord(c) * (idx + 1) for idx, c in enumerate(repo_name))
    palette_idx = hash_val % len(REPO_PALETTES)
    color_idx = 0 if is_dark else 2
    return REPO_PALETTES[palette_idx][color_idx]


@router.get("/repos")
async def list_my_repos(
    per_page: int = Query(30, le=100),
    is_dark: bool = Query(True, description="Usar colores claros para tema oscuro"),
):
    repos = await _fetch("/user/repos", {"per_page": per_page, "sort": "updated"})
    return {
        "repos": [
            {
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "color": get_repo_color(r["full_name"], is_dark),
            }
            for r in repos
        ]
    }
