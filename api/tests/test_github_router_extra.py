"""Extra coverage for ``routers/integrations/github.py`` (#1401).

``test_github.py`` pins auth/webhook/OAuth-state paths; this file covers the
rest: repo CRUD against the DB, aggregated issues/pulls, repo-scoped issue
and comment endpoints, sync, DB items/events, webhook payload validation,
and the OAuth device/web error branches. All GitHub HTTP is mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItem,
    GitHubItemType,
    GitHubRepo,
)
from models.goal import Goal
from services import oauth_state

GH = "/integrations/github"


@pytest.fixture(autouse=True)
def _clear_github_cache():
    """The router caches upstream responses (#1512) — isolate each test."""
    from routers.integrations import github as gh_router

    gh_router.clear_github_cache()
    yield
    gh_router.clear_github_cache()


def _resp(json_data):
    r = MagicMock()
    r.json.return_value = json_data
    r.raise_for_status.return_value = None
    return r


def _status_error(status: int, json_data=None):
    request = MagicMock()
    response = MagicMock()
    response.status_code = status
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("not json")
    return httpx.HTTPStatusError(f"status {status}", request=request, response=response)


def _get_dispatch(routes):
    """Build an httpx.AsyncClient.get side_effect from (substr, payload) pairs.

    ``payload`` is returned via ``_resp``; an Exception instance is raised.
    First matching substring wins — order most-specific first.
    """

    def _get(url, **kwargs):
        for substr, payload in routes:
            if substr in url:
                if isinstance(payload, Exception):
                    raise payload
                return _resp(payload)
        raise AssertionError(f"unexpected GET {url}")

    return _get


def _repo(db, full_name="octocat/Repo-One", **kwargs) -> GitHubRepo:
    repo = GitHubRepo(
        name=full_name.split("/")[-1],
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        **kwargs,
    )
    db.add(repo)
    db.flush()
    return repo


def _item(db, repo_id, **kwargs) -> GitHubItem:
    item = GitHubItem(
        repo_id=repo_id,
        external_id=kwargs.pop("external_id", 1),
        item_type=kwargs.pop("item_type", GitHubItemType.ISSUE),
        number=kwargs.pop("number", 1),
        title=kwargs.pop("title", "item"),
        url="https://api.github.com/x",
        html_url="https://github.com/o/r/issues/1",
        **kwargs,
    )
    db.add(item)
    db.flush()
    return item


def _issue(number=1, login="octocat", html_url=None, **kw):
    return {
        "id": 1000 + number,
        "number": number,
        "title": f"issue {number}",
        "body": "body",
        "state": kw.pop("state", "open"),
        "html_url": html_url or f"https://github.com/octocat/Repo-One/issues/{number}",
        "labels": [{"name": "bug"}],
        "user": {"login": login},
        "assignee": {"login": "assignee-user"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        **kw,
    }


# ─── status / user / repos ────────────────────────────────────────────────────


def test_status_token_fetch_failure(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    get = AsyncMock(side_effect=httpx.ConnectError("down"))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "username": None}


def test_status_username_fetch_failure(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")
    get = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/status")
    assert resp.json() == {"connected": False, "username": None}


def test_user_endpoint_modes(client, monkeypatch):
    # No config → 400
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    assert client.get(f"{GH}/user").status_code == 400

    # Username-only → unauthenticated public lookup
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")
    get = AsyncMock(return_value=_resp({"login": "octocat"}))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/user")
    assert resp.status_code == 200
    assert "/users/octocat" in get.call_args.args[0]

    # Token mode → /user
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    get2 = AsyncMock(return_value=_resp({"login": "tok-user"}))
    with patch("httpx.AsyncClient.get", new=get2):
        resp = client.get(f"{GH}/user")
    assert resp.json()["login"] == "tok-user"
    assert get2.call_args.args[0].endswith("/user")


def test_repos_token_and_empty_modes(client, monkeypatch):
    # Token mode maps repo fields + color
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    repo_data = {
        "id": 1,
        "name": "Repo-One",
        "full_name": "octocat/Repo-One",
        "description": "d",
        "private": False,
        "html_url": "https://github.com/octocat/Repo-One",
        "default_branch": "main",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    get = AsyncMock(return_value=_resp([repo_data]))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/repos", params={"is_dark": "false"})
    assert resp.status_code == 200
    repos = resp.json()["repos"]
    assert repos[0]["full_name"] == "octocat/Repo-One"
    assert repos[0]["color"].startswith("#")

    # No config → empty list without HTTP
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    resp = client.get(f"{GH}/repos")
    assert resp.json() == {"repos": []}


def test_get_repo_endpoint(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    get = AsyncMock(return_value=_resp({"full_name": "octocat/Repo-One"}))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/repos/octocat/Repo-One")
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "octocat/Repo-One"

    # Unsafe owner/repo segments are rejected before any HTTP call
    resp = client.get(f"{GH}/repos/..%2F..%2Fevil/x")
    assert resp.status_code in (400, 404, 422)


# ─── repos in DB ──────────────────────────────────────────────────────────────


def test_add_repo_to_db_success(client, db_session, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    gh_data = {
        "full_name": "octocat/New-Repo",
        "description": "fresh",
        "html_url": "https://github.com/octocat/New-Repo",
        "default_branch": "dev",
        "private": True,
    }
    get = AsyncMock(return_value=_resp(gh_data))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.post(f"{GH}/repos/db", params={"full_name": "octocat/New-Repo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "octocat/New-Repo"
    row = db_session.query(GitHubRepo).filter(GitHubRepo.full_name == "octocat/New-Repo").one()
    assert row.is_private is True and row.default_branch == "dev"


def test_add_repo_to_db_github_404(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    get = AsyncMock(side_effect=_status_error(404))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.post(f"{GH}/repos/db", params={"full_name": "octocat/Missing"})
    assert resp.status_code == 404


def test_add_repo_to_db_duplicate_and_bad_format(client, db_session, monkeypatch):
    _repo(db_session, "octocat/Dup")
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    get = AsyncMock(return_value=_resp({"full_name": "octocat/Dup", "html_url": "u"}))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.post(f"{GH}/repos/db", params={"full_name": "octocat/Dup"})
    assert resp.status_code == 400
    assert "already tracked" in resp.json()["detail"]

    # Malformed full_name (no owner/repo split) → 400 before HTTP
    resp = client.post(f"{GH}/repos/db", params={"full_name": "noslash"})
    assert resp.status_code == 400


def test_list_and_remove_repos_in_db(client, db_session):
    repo = _repo(db_session, "octocat/Listed")
    item = _item(db_session, repo.id, external_id=9)
    db_session.commit()

    resp = client.get(f"{GH}/repos/db")
    assert resp.status_code == 200
    names = [r["full_name"] for r in resp.json()["repos"]]
    assert "octocat/Listed" in names

    # Missing repo → 404
    assert client.delete(f"{GH}/repos/db/999999").status_code == 404

    # Existing repo → cascades items manually then deletes
    resp = client.delete(f"{GH}/repos/db/{repo.id}")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "repo_id": repo.id}
    assert db_session.get(GitHubRepo, repo.id) is None
    assert db_session.get(GitHubItem, item.id) is None


# ─── aggregated issues / pulls (Search API, #1512) ────────────────────────────
#
# /issues and /pulls resolve through GET /search/issues — one call for the
# items page plus lightweight total/open count queries — instead of the old
# per-repo gather. Search results carry `repository_url` instead of the
# `_repo_full_name` the fan-out injected.


def _token_mode(monkeypatch, username="octocat"):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")


def _search_item(number=1, repo="octocat/Repo-One", **kw):
    item = _issue(number, **kw)
    item["repository_url"] = f"https://api.github.com/repos/{repo}"
    return item


def _search_resp(items, total=None):
    return {"total_count": len(items) if total is None else total, "items": items}


def _search_dispatch(seen_calls, items=None, total=None, open_total=0):
    """Dispatch the search flow: /user → login, /search/issues → routed on q."""

    def _get(url, **kwargs):
        seen_calls.append(url)
        params = kwargs.get("params") or {}
        if "/search/issues" in url:
            # Items page uses the caller's per_page; count queries use 1.
            if params.get("per_page", 1) == 1:
                return _resp({"total_count": open_total, "items": []})
            return _resp(_search_resp(items or [], total))
        if url.endswith("/user"):
            return _resp({"login": "octocat"})
        raise AssertionError(f"unexpected GET {url}")

    return _get


def test_my_issues_created_uses_search_no_fanout(client, monkeypatch):
    _token_mode(monkeypatch)
    item = _search_item(1, state="open")
    calls: list[str] = []
    get = AsyncMock(side_effect=_search_dispatch(calls, items=[item], total=1, open_total=1))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/issues", params={"filter": "created"})
    assert resp.status_code == 200
    data = resp.json()
    assert [i["number"] for i in data["issues"]] == [1]
    assert data["issues"][0]["repo"] == "octocat/Repo-One"
    assert data["stats"] == {"total": 1, "open": 1, "closed": 0}
    assert data["filter"] == "created"
    # #1512 — no per-repo fan-out: /user + ≤2 search calls, nothing else.
    assert len(calls) <= 3
    assert not any("/repos/" in c for c in calls)


def test_my_issues_filter_and_state_qualifiers(client, monkeypatch):
    _token_mode(monkeypatch)
    queries: list[str] = []

    def _get(url, **kwargs):
        params = kwargs.get("params") or {}
        if "/search/issues" in url:
            queries.append(params.get("q", ""))
            return _resp({"total_count": 0, "items": []})
        if url.endswith("/user"):
            return _resp({"login": "octocat"})
        raise AssertionError(f"unexpected GET {url}")

    get = AsyncMock(side_effect=_get)
    with patch("httpx.AsyncClient.get", new=get):
        client.get(f"{GH}/issues", params={"filter": "created"})
    assert any(q == "type:issue author:octocat" for q in queries)

    queries.clear()
    get1 = AsyncMock(side_effect=_get)
    with patch("httpx.AsyncClient.get", new=get1):
        resp = client.get(f"{GH}/issues", params={"filter": "assigned"})
    assert resp.status_code == 200
    assert resp.json()["filter"] == "assigned"
    assert any(q == "type:issue assignee:octocat" for q in queries)
    assert any(q == "type:issue assignee:octocat is:open" for q in queries)

    # filter=all + state=closed → involves: + is:closed on the items query
    queries.clear()
    get2 = AsyncMock(side_effect=_get)
    with patch("httpx.AsyncClient.get", new=get2):
        client.get(f"{GH}/issues", params={"filter": "all", "state": "closed"})
    assert any("type:issue involves:octocat is:closed" in q for q in queries)


def test_my_issues_username_mode_and_search_error(client, monkeypatch):
    _token_mode(monkeypatch)

    # Search failure degrades to the empty payload, not a 500
    get = AsyncMock(side_effect=RuntimeError("api down"))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/issues")
    assert resp.status_code == 200
    assert resp.json()["issues"] == []

    # Username-only mode: no /user lookup, unauthenticated search
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")
    calls: list[str] = []
    get2 = AsyncMock(side_effect=_search_dispatch(calls, items=[_search_item(9, repo="octocat/R9")]))
    with patch("httpx.AsyncClient.get", new=get2):
        resp = client.get(f"{GH}/issues")
    assert resp.status_code == 200
    assert resp.json()["issues"][0]["repo"] == "octocat/R9"
    assert not any(c.endswith("/user") for c in calls)

    # No config at all → empty payload, no HTTP
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    calls.clear()
    get3 = AsyncMock(side_effect=_search_dispatch(calls))
    with patch("httpx.AsyncClient.get", new=get3):
        resp = client.get(f"{GH}/issues")
    assert resp.json()["issues"] == []
    assert resp.json()["stats"]["total"] == 0
    assert calls == []


def test_my_pulls_search_maps_draft_and_merged(client, monkeypatch):
    _token_mode(monkeypatch)
    pull = {
        "id": 50,
        "number": 7,
        "title": "pr seven",
        "state": "open",
        "draft": True,
        "html_url": "https://github.com/octocat/R1/pull/7",
        "repository_url": "https://api.github.com/repos/octocat/R1",
        "pull_request": {"merged_at": None},
        "user": {"login": "octocat"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    calls: list[str] = []
    get = AsyncMock(side_effect=_search_dispatch(calls, items=[pull], total=1, open_total=1))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/pulls", params={"filter": "all"})
    data = resp.json()
    assert data["pulls"][0]["number"] == 7
    assert data["pulls"][0]["draft"] is True
    assert data["pulls"][0]["repo"] == "octocat/R1"
    assert data["stats"]["draft"] == 1
    assert len(calls) <= 4  # /user + ≤3 search queries


def test_my_pulls_username_mode_and_empty(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")
    pull_min = {
        "id": 1,
        "number": 2,
        "title": "t",
        "state": "closed",
        "html_url": "u",
        "repository_url": "https://api.github.com/repos/octocat/R2",
        "pull_request": {"merged_at": "2026-01-03T00:00:00Z"},
        "user": {"login": "x"},
        "created_at": "c",
        "updated_at": "u",
    }
    calls: list[str] = []
    get = AsyncMock(side_effect=_search_dispatch(calls, items=[pull_min]))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/pulls")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pulls"][0]["number"] == 2
    assert data["pulls"][0]["merged_at"] == "2026-01-03T00:00:00Z"

    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    resp = client.get(f"{GH}/pulls")
    assert resp.json()["pulls"] == []


# ─── repo-scoped issues / comments / pulls / commits ─────────────────────────


def test_repo_issues_and_issue_detail(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    get = AsyncMock(return_value=_resp([_issue(3), _issue(4, state="closed")]))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/repos/octocat/Repo-One/issues", params={"state": "all"})
    assert resp.status_code == 200
    issues = resp.json()["issues"]
    assert len(issues) == 2
    assert issues[0]["labels"] == ["bug"]
    assert issues[0]["assignee"] == "assignee-user"

    get2 = AsyncMock(return_value=_resp(_issue(3)))
    with patch("httpx.AsyncClient.get", new=get2):
        resp = client.get(f"{GH}/repos/octocat/Repo-One/issues/3")
    assert resp.json()["number"] == 3


def test_create_update_close_issue(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    created = {"id": 1, "number": 10, "title": "new", "html_url": "u", "state": "open"}
    post = AsyncMock(return_value=_resp(created))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(
            f"{GH}/repos/octocat/Repo-One/issues",
            json={"title": "new", "body": "b", "labels": ["bug"]},
        )
    assert resp.status_code == 200
    assert resp.json()["number"] == 10
    sent = post.call_args.kwargs["json"]
    assert sent == {"title": "new", "body": "b", "labels": ["bug"]}

    patch_m = AsyncMock(return_value=_resp({"id": 1, "number": 10, "title": "renamed", "state": "open"}))
    with patch("httpx.AsyncClient.patch", new=patch_m):
        resp = client.patch(
            f"{GH}/repos/octocat/Repo-One/issues/10",
            params={"title": "renamed", "state": "open", "labels": ["x"]},
        )
    assert resp.status_code == 200
    assert resp.json()["title"] == "renamed"
    assert patch_m.call_args.kwargs["json"]["state"] == "open"

    patch_m2 = AsyncMock(return_value=_resp({"number": 10, "state": "closed"}))
    with patch("httpx.AsyncClient.patch", new=patch_m2):
        resp = client.post(f"{GH}/repos/octocat/Repo-One/issues/10/close")
    assert resp.json() == {"number": 10, "state": "closed"}
    assert patch_m2.call_args.kwargs["json"] == {"state": "closed"}


def test_comments_endpoints(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    get = AsyncMock(
        return_value=_resp([{"id": 5, "body": "nice", "user": {"login": "octocat"}, "created_at": "2026-01-01"}])
    )
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/repos/octocat/Repo-One/issues/3/comments")
    assert resp.json()["comments"][0]["author"] == "octocat"

    post = AsyncMock(return_value=_resp({"id": 6, "body": "thanks"}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(f"{GH}/repos/octocat/Repo-One/issues/3/comments", json={"body": "thanks"})
    assert resp.json() == {"id": 6, "body": "thanks"}


def test_repo_pulls_and_commits(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    get = AsyncMock(
        return_value=_resp(
            [
                {
                    "id": 8,
                    "number": 2,
                    "title": "pr",
                    "state": "open",
                    "html_url": "u",
                    "user": {"login": "octocat"},
                    "draft": False,
                    "created_at": "c",
                    "updated_at": "u",
                }
            ]
        )
    )
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.get(f"{GH}/repos/octocat/Repo-One/pulls")
    assert resp.json()["pulls"][0]["number"] == 2

    commit = {
        "sha": "abc123",
        "commit": {"message": "msg", "author": {"name": "Dev", "date": "2026-01-01"}},
        "html_url": "https://github.com/octocat/Repo-One/commit/abc123",
    }
    get2 = AsyncMock(return_value=_resp([commit]))
    with patch("httpx.AsyncClient.get", new=get2):
        resp = client.get(f"{GH}/repos/octocat/Repo-One/commits", params={"sha": "main"})
    data = resp.json()["commits"]
    assert data[0]["sha"] == "abc123"
    assert data[0]["author"] == "Dev"
    assert get2.call_args.kwargs["params"]["sha"] == "main"


def test_repo_scoped_endpoints_require_token(client, monkeypatch):
    """Without token or username, _headers(optional=False) → 400."""
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")
    resp = client.get(f"{GH}/repos/octocat/Repo-One/issues")
    assert resp.status_code == 400
    assert "token" in resp.json()["detail"].lower()


# ─── DB items / events / goal links ───────────────────────────────────────────


def test_items_in_db_filters(client, db_session):
    repo = _repo(db_session, "octocat/Items")
    goal = Goal(title="linked goal")
    db_session.add(goal)
    db_session.flush()
    wanted = _item(db_session, repo.id, external_id=1, goal_id=goal.id, number=11)
    other = _item(db_session, repo.id, external_id=2, number=12)
    db_session.commit()

    resp = client.get(f"{GH}/db/items", params={"repo_id": repo.id})
    assert {i["id"] for i in resp.json()["items"]} == {wanted.id, other.id}

    resp = client.get(f"{GH}/db/items", params={"goal_id": goal.id})
    items = resp.json()["items"]
    assert [i["id"] for i in items] == [wanted.id]
    assert items[0]["goal_id"] == goal.id


def test_link_and_unlink_goal_endpoint(client, db_session):
    repo = _repo(db_session, "octocat/LinkMe")
    goal = Goal(title="g")
    db_session.add(goal)
    db_session.flush()
    item = _item(db_session, repo.id)
    db_session.commit()

    resp = client.post(f"{GH}/db/items/{item.id}/link-goal", params={"goal_id": goal.id})
    assert resp.status_code == 200
    assert resp.json() == {"item_id": item.id, "goal_id": goal.id}
    assert db_session.get(GitHubItem, item.id).goal_id == goal.id

    resp = client.delete(f"{GH}/db/items/{item.id}/link-goal")
    assert resp.status_code == 200
    assert resp.json()["goal_id"] is None

    assert client.post(f"{GH}/db/items/999999/link-goal", params={"goal_id": 1}).status_code == 404
    assert client.delete(f"{GH}/db/items/999999/link-goal").status_code == 404


def test_events_in_db(client, db_session):
    repo = _repo(db_session, "octocat/Events")
    other = _repo(db_session, "octocat/Other")
    db_session.add_all(
        [
            GitHubEvent(
                repo_id=repo.id,
                event_type=GitHubEventType.ISSUES,
                action="opened",
                sender="octocat",
                payload={},
            ),
            GitHubEvent(
                repo_id=other.id,
                event_type=GitHubEventType.PUSH,
                action="",
                sender="bot",
                payload={},
            ),
        ]
    )
    db_session.commit()

    resp = client.get(f"{GH}/db/events")
    assert resp.status_code == 200
    assert len(resp.json()["events"]) == 2

    resp = client.get(f"{GH}/db/events", params={"repo_id": repo.id})
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "issues"
    assert events[0]["sender"] == "octocat"


# ─── webhook payload validation ───────────────────────────────────────────────


def test_webhook_rejects_invalid_json(client):
    resp = client.post(
        f"{GH}/webhook",
        content=b"{not-json",
        headers={"X-GitHub-Event": "issues"},
    )
    assert resp.status_code == 400
    assert "Invalid JSON" in resp.json()["detail"]


def test_webhook_rejects_non_dict_payload(client):
    resp = client.post(
        f"{GH}/webhook",
        content=b"[1, 2, 3]",
        headers={"X-GitHub-Event": "issues"},
    )
    assert resp.status_code == 400
    assert "Invalid webhook payload" in resp.json()["detail"]


# ─── sync_repo ────────────────────────────────────────────────────────────────


def _gh_issue_payload(external_id, number, **kw):
    return {
        "id": external_id,
        "number": number,
        "title": kw.pop("title", f"issue {number}"),
        "body": "b",
        "state": kw.pop("state", "open"),
        "labels": [{"name": "bug"}, {"name": "ui"}],
        "user": {"login": "octocat"},
        "assignee": {"login": "assignee-user"},
        "url": f"https://api.github.com/x/{external_id}",
        "html_url": f"https://github.com/octocat/R/issues/{number}",
        **kw,
    }


def test_sync_repo_not_found_and_bad_name(client, db_session):
    assert client.post(f"{GH}/sync/repo/999999").status_code == 404

    bad = _repo(db_session, "octocat/Bad")
    bad.full_name = "no-slash-here"
    db_session.commit()
    resp = client.post(f"{GH}/sync/repo/{bad.id}")
    assert resp.status_code == 400
    assert "Invalid repo full_name" in resp.json()["detail"]


def test_sync_repo_github_error(client, db_session, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    repo = _repo(db_session, "octocat/SyncErr")
    db_session.commit()
    get = AsyncMock(side_effect=httpx.ConnectError("down"))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.post(f"{GH}/sync/repo/{repo.id}")
    assert resp.status_code == 502


def test_sync_repo_upserts_items(client, db_session, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok")
    repo = _repo(db_session, "octocat/SyncMe")
    existing = _item(
        db_session,
        repo.id,
        external_id=100,
        number=1,
        title="old title",
        state="open",
    )
    db_session.commit()

    issues = [
        _gh_issue_payload(100, 1, title="renamed upstream", state="closed"),
        _gh_issue_payload(101, 2, title="brand new"),
    ]
    get = AsyncMock(return_value=_resp(issues))
    with patch("httpx.AsyncClient.get", new=get):
        resp = client.post(f"{GH}/sync/repo/{repo.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["synced"] == 2
    assert data["repo_id"] == repo.id
    assert data["last_synced_at"]

    db_session.expire_all()
    updated = db_session.get(GitHubItem, existing.id)
    assert updated.title == "renamed upstream"
    assert updated.state == "closed"
    assert updated.labels == "bug,ui"

    created = db_session.query(GitHubItem).filter(GitHubItem.repo_id == repo.id, GitHubItem.external_id == 101).one()
    assert created.title == "brand new"
    assert created.item_type == GitHubItemType.ISSUE
    assert repo.last_synced_at is not None


# ─── OAuth device flow error branches ─────────────────────────────────────────


def _device_start(monkeypatch, client_id="cid", secret_key="test-secret"):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", client_id)
    monkeypatch.setattr("config.settings.secret_key", secret_key)


def test_device_start_no_client_id(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "")
    assert client.get(f"{GH}/oauth/device/start").status_code == 400


def test_device_start_http_status_error(client, monkeypatch):
    _device_start(monkeypatch)
    err = _status_error(400, {"error_description": "client is invalid"})
    post = AsyncMock(side_effect=err)
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/device/start")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "client is invalid"


def test_device_start_status_error_non_json(client, monkeypatch):
    _device_start(monkeypatch)
    err = _status_error(500)
    post = AsyncMock(side_effect=err)
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/device/start")
    assert resp.status_code == 400
    assert "500" in resp.json()["detail"]


def test_device_start_generic_error(client, monkeypatch):
    _device_start(monkeypatch)
    post = AsyncMock(side_effect=httpx.ConnectError("no route"))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/device/start")
    assert resp.status_code == 502
    assert "Failed to communicate" in resp.json()["detail"]


def test_device_start_error_payload(client, monkeypatch):
    _device_start(monkeypatch)
    post = AsyncMock(return_value=_resp({"error": "validation_failed", "error_description": "bad scope"}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/device/start")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad scope"


def test_device_start_missing_device_code(client, monkeypatch):
    _device_start(monkeypatch)
    post = AsyncMock(return_value=_resp({"user_code": "ABCD-1234"}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/device/start")
    assert resp.status_code == 502
    assert "device code" in resp.json()["detail"]


def test_device_start_seal_failure(client, monkeypatch):
    """GitHub returns a device_code but SECRET_KEY is missing → 400."""
    _device_start(monkeypatch, secret_key="")
    post = AsyncMock(return_value=_resp({"device_code": "dc", "user_code": "UC"}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/device/start")
    assert resp.status_code == 400
    assert "SECRET_KEY" in resp.json()["detail"]


# ─── OAuth device polling error branches ──────────────────────────────────────


def _poll_token(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    return oauth_state.seal_value("github-device", "device-code-xyz")


def test_device_polling_no_client_id(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "")
    resp = client.post(f"{GH}/oauth/device/polling", json={"poll_token": "whatever"})
    assert resp.status_code == 400


def test_device_polling_github_error_states(client, monkeypatch):
    _device_start(monkeypatch)
    token = _poll_token(monkeypatch)

    cases = [
        ({"error": "slowdown"}, "slowdown"),
        ({"error": "expired_token"}, "expired"),
        ({"error": "access_denied"}, "denied"),
        ({"error": "unknown_thing", "error_description": "mystery"}, "error"),
    ]
    for payload, expected_status in cases:
        post = AsyncMock(return_value=_resp(payload))
        with patch("httpx.AsyncClient.post", new=post):
            resp = client.post(f"{GH}/oauth/device/polling", json={"poll_token": token})
        assert resp.status_code == 200
        assert resp.json()["status"] == expected_status


def test_device_polling_http_and_generic_errors(client, monkeypatch):
    _device_start(monkeypatch)
    token = _poll_token(monkeypatch)

    err = _status_error(400, {"error_description": "poll failed"})
    post = AsyncMock(side_effect=err)
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(f"{GH}/oauth/device/polling", json={"poll_token": token})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "poll failed"

    post2 = AsyncMock(side_effect=httpx.ConnectError("down"))
    with patch("httpx.AsyncClient.post", new=post2):
        resp = client.post(f"{GH}/oauth/device/polling", json={"poll_token": token})
    assert resp.status_code == 502


def test_device_polling_authorized(client, monkeypatch):
    _device_start(monkeypatch)
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "sec")
    token = _poll_token(monkeypatch)
    post = AsyncMock(
        return_value=_resp({"access_token": "gho_abc", "token_type": "bearer", "scope": "public_repo read:user"})
    )
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(f"{GH}/oauth/device/polling", json={"poll_token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "authorized"
    assert data["access_token"] == "gho_abc"
    assert data["scope"] == "public_repo read:user"


# ─── OAuth web flow / callback / revoke ───────────────────────────────────────


def _web_flow_config(monkeypatch, client_id="cid", web_url="https://app.example.com/gh/cb", secret_key="test-secret"):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", client_id)
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "csec")
    monkeypatch.setattr("routers.integrations.github.settings.github_oauth_web_url", web_url)
    monkeypatch.setattr("config.settings.secret_key", secret_key)


def test_web_start_missing_config(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "")
    assert client.get(f"{GH}/oauth/web/start").status_code == 400

    _web_flow_config(monkeypatch, web_url="")
    resp = client.get(f"{GH}/oauth/web/start")
    assert resp.status_code == 400
    assert "redirect URI" in resp.json()["detail"]


def test_web_start_state_failure(client, monkeypatch):
    _web_flow_config(monkeypatch, secret_key="")
    resp = client.get(f"{GH}/oauth/web/start")
    assert resp.status_code == 400
    assert "SECRET_KEY" in resp.json()["detail"]


def test_web_start_success(client, monkeypatch):
    _web_flow_config(monkeypatch)
    resp = client.get(f"{GH}/oauth/web/start")
    assert resp.status_code == 200
    data = resp.json()
    assert "authorize_url" in data and "state" in data
    assert "client_id=cid" in data["authorize_url"]


def test_callback_error_param(client):
    resp = client.get(f"{GH}/oauth/callback", params={"code": "x", "error": "access_denied"})
    assert resp.status_code == 400
    assert "access_denied" in resp.json()["detail"]


def test_callback_missing_client_config(client, monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    state = oauth_state.generate_state("github")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "")
    resp = client.get(f"{GH}/oauth/callback", params={"code": "c", "state": state})
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


def test_callback_token_exchange_error(client, monkeypatch):
    _web_flow_config(monkeypatch)
    state = oauth_state.generate_state("github")
    post = AsyncMock(return_value=_resp({"error": "bad_code", "error_description": "code expired"}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/callback", params={"code": "c", "state": state})
    assert resp.status_code == 400
    assert "code expired" in resp.json()["detail"]


def test_callback_success(client, monkeypatch):
    _web_flow_config(monkeypatch)
    state = oauth_state.generate_state("github")
    post = AsyncMock(return_value=_resp({"access_token": "gho_xyz", "token_type": "bearer", "scope": "public_repo"}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"{GH}/oauth/callback", params={"code": "good-code", "state": state})
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "gho_xyz"


def test_revoke_without_token(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    resp = client.post(f"{GH}/oauth/revoke", json={})
    assert resp.status_code == 400
    assert "No GitHub token" in resp.json()["detail"]


def test_revoke_success(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "tok-to-kill")
    post = AsyncMock(return_value=_resp({}))
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(f"{GH}/oauth/revoke", json={})
    assert resp.status_code == 200
    assert resp.json() == {"status": "revoked"}
    # The configured token is what gets revoked when body omits it
    assert post.call_args.kwargs["data"]["access_token"] == "tok-to-kill"
