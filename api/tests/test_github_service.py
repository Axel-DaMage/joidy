"""Coverage for ``services/github_service.py`` (#1401).

The service is a thin layer over ``http_client`` plus the GitHub DB
repositories; these tests pin every wrapper, the DB helpers, webhook-event
processing and goal linking. All HTTP is mocked — no real network access.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItem,
    GitHubItemType,
    GitHubRepo,
)
from models.goal import Goal
from services import github_service as svc


def _run(coro):
    return asyncio.run(coro)


def _http_mock(**verbs):
    """Mock for ``services.github_service.http_client``.

    Returns an async-context-manager mock whose client exposes the given
    AsyncMock verbs (``get``, ``post``, ``patch``, ``delete``).
    """
    instance = MagicMock()
    for name, mock in verbs.items():
        setattr(instance, name, mock)
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    return instance


def _resp(json_data):
    r = MagicMock()
    r.json.return_value = json_data
    r.raise_for_status.return_value = None
    return r


def _patch_http(**verbs):
    return patch("services.github_service.http_client", return_value=_http_mock(**verbs))


def _repo(db, full_name="octocat/Hello-World", **kwargs) -> GitHubRepo:
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
        url="https://github.com/o/r/issues/1",
        html_url="https://github.com/o/r/issues/1",
        **kwargs,
    )
    db.add(item)
    db.flush()
    return item


# ─── HTTP helpers ─────────────────────────────────────────────────────────────


def test_headers_requires_token(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "")
    with pytest.raises(ValueError, match="token not configured"):
        svc._headers()


def test_headers_with_token(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok123")
    headers = svc._headers()
    assert headers["Authorization"] == "Bearer tok123"
    assert headers["Accept"] == "application/vnd.github+json"


def test_fetch_github_gets_and_parses(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    get = AsyncMock(return_value=_resp([{"id": 1}]))
    with _patch_http(get=get):
        result = _run(svc.fetch_github("/user/repos", {"per_page": 5}))
    assert result == [{"id": 1}]
    url = get.call_args.args[0]
    assert url == "https://api.github.com/user/repos"
    assert get.call_args.kwargs["params"] == {"per_page": 5}


def test_post_github(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    post = AsyncMock(return_value=_resp({"id": 7}))
    with _patch_http(post=post):
        result = _run(svc.post_github("/repos/o/r/issues", {"title": "t"}))
    assert result == {"id": 7}
    assert post.call_args.kwargs["json"] == {"title": "t"}


def test_patch_github(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    patch_m = AsyncMock(return_value=_resp({"state": "closed"}))
    with _patch_http(patch=patch_m):
        result = _run(svc.patch_github("/repos/o/r/issues/3", {"state": "closed"}))
    assert result == {"state": "closed"}


def test_delete_github(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    delete = AsyncMock(return_value=_resp({}))
    with _patch_http(delete=delete):
        _run(svc.delete_github("/repos/o/r/hooks/9"))
    assert delete.call_args.args[0] == "https://api.github.com/repos/o/r/hooks/9"


# ─── API wrappers ─────────────────────────────────────────────────────────────


def test_read_wrappers_hit_expected_endpoints(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    get = AsyncMock(return_value=_resp({}))
    with _patch_http(get=get):
        _run(svc.get_user())
        assert get.call_args.args[0].endswith("/user")
        _run(svc.get_repos())
        assert "/user/repos" in get.call_args.args[0]
        _run(svc.get_repo("o", "r"))
        assert get.call_args.args[0].endswith("/repos/o/r")
        _run(svc.get_issues("o", "r", state="closed"))
        assert get.call_args.kwargs["params"]["state"] == "closed"
        _run(svc.get_pulls("o", "r"))
        assert get.call_args.args[0].endswith("/repos/o/r/pulls")
        _run(svc.get_issue("o", "r", 4))
        assert get.call_args.args[0].endswith("/repos/o/r/issues/4")
        _run(svc.get_pull("o", "r", 5))
        assert get.call_args.args[0].endswith("/repos/o/r/pulls/5")
        _run(svc.get_comments("o", "r", 6))
        assert get.call_args.args[0].endswith("/repos/o/r/issues/6/comments")
        _run(svc.get_commits("o", "r", per_page=7))
        assert get.call_args.kwargs["params"]["per_page"] == 7
        _run(svc.get_file_content("o", "r", "README.md"))
        assert get.call_args.args[0].endswith("/repos/o/r/contents/README.md")


def test_create_issue_variants(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    post = AsyncMock(return_value=_resp({"id": 1}))
    with _patch_http(post=post):
        _run(svc.create_issue("o", "r", "title only"))
        assert post.call_args.kwargs["json"] == {"title": "title only"}
        _run(svc.create_issue("o", "r", "full", body="b", labels=["bug"]))
        assert post.call_args.kwargs["json"] == {"title": "full", "body": "b", "labels": ["bug"]}


def test_update_issue_builds_payload(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    patch_m = AsyncMock(return_value=_resp({}))
    with _patch_http(patch=patch_m):
        _run(svc.update_issue("o", "r", 1, title="t", state="open", labels=["x"]))
        sent = patch_m.call_args.kwargs["json"]
        assert sent == {"title": "t", "state": "open", "labels": ["x"]}
        # close_issue delegates with state=closed only
        _run(svc.close_issue("o", "r", 2))
        assert patch_m.call_args.kwargs["json"] == {"state": "closed"}


def test_create_comment_and_webhook(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    post = AsyncMock(return_value=_resp({"id": 1}))
    with _patch_http(post=post):
        _run(svc.create_comment("o", "r", 3, "hi"))
        assert post.call_args.kwargs["json"] == {"body": "hi"}
        _run(svc.create_webhook("o", "r", "https://api.example.com/hook", "s3cr3t"))
        sent = post.call_args.kwargs["json"]
        assert sent["config"]["secret"] == "s3cr3t"
        assert "issues" in sent["events"] and sent["active"] is True


def test_delete_webhook(monkeypatch):
    monkeypatch.setattr("config.settings.github_token", "tok")
    delete = AsyncMock(return_value=_resp({}))
    with _patch_http(delete=delete):
        _run(svc.delete_webhook("o", "r", 11))
    assert delete.call_args.args[0].endswith("/repos/o/r/hooks/11")


# ─── DB helpers ───────────────────────────────────────────────────────────────


def test_create_repo_in_db_new_and_existing(db_session):
    repo = svc.create_repo_in_db(db_session, "octocat/New-Repo", description="d")
    assert isinstance(repo, GitHubRepo)
    assert repo.full_name == "octocat/New-Repo"
    assert repo.name == "New-Repo"

    # Second call for the same full_name returns the persisted row.
    _repo(db_session, "octocat/Tracked")
    existing = svc.create_repo_in_db(db_session, "octocat/Tracked")
    assert existing.id is not None


def test_create_repo_in_db_rejects_bad_format(db_session):
    with pytest.raises(ValueError, match="Invalid repo full_name"):
        svc.create_repo_in_db(db_session, "no-slash")


def test_sync_placeholders_return_none(db_session):
    assert svc.sync_repos_to_db(db_session) is None
    assert svc.sync_issues_to_db(db_session, 1, "o/r") is None


def test_link_and_unlink_goal(db_session):
    repo = _repo(db_session)
    goal = Goal(title="ship it")
    db_session.add(goal)
    db_session.flush()
    item = _item(db_session, repo.id, external_id=42)

    linked = svc.link_goal_to_issue(db_session, goal.id, item.id)
    assert linked is not None and linked.goal_id == goal.id

    unlinked = svc.unlink_goal_from_issue(db_session, item.id)
    assert unlinked is not None and unlinked.goal_id is None

    assert svc.link_goal_to_issue(db_session, goal.id, 999999) is None
    assert svc.unlink_goal_from_issue(db_session, 999999) is None


def test_record_event_persists(db_session):
    repo = _repo(db_session)
    event = svc.record_event(
        db_session,
        repo.id,
        GitHubEventType.ISSUES,
        "opened",
        "octocat",
        {"k": "v"},
        item_type=GitHubItemType.ISSUE,
        item_number=3,
        item_external_id=99,
    )
    assert event.id is not None
    row = db_session.query(GitHubEvent).filter(GitHubEvent.id == event.id).one()
    assert row.item_number == 3 and row.payload == {"k": "v"}


def test_process_webhook_event_unknown_repo(db_session):
    assert svc.process_webhook_event(db_session, "ghost/none", GitHubEventType.ISSUES, "opened", "x", {}) is None


def test_process_webhook_event_issues_and_pr(db_session):
    repo = _repo(db_session)

    issue_event = svc.process_webhook_event(
        db_session,
        repo.full_name,
        GitHubEventType.ISSUES,
        "opened",
        "octocat",
        {"issue": {"number": 7, "id": 70}},
    )
    assert issue_event.item_type == GitHubItemType.ISSUE
    assert issue_event.item_number == 7 and issue_event.item_external_id == 70

    pr_event = svc.process_webhook_event(
        db_session,
        repo.full_name,
        GitHubEventType.PULL_REQUEST,
        "opened",
        "octocat",
        {"pull_request": {"number": 8, "id": 80}},
    )
    assert pr_event.item_type == GitHubItemType.PR
    assert pr_event.item_number == 8

    # push events carry no item metadata
    push_event = svc.process_webhook_event(db_session, repo.full_name, GitHubEventType.PUSH, "", "octocat", {})
    assert push_event.item_type is None and push_event.item_number is None


def test_webhook_secret_and_setup(db_session, monkeypatch):
    secret = svc.get_webhook_secret()
    assert isinstance(secret, str) and len(secret) == 64

    # Malformed full_name → None, no HTTP call.
    assert _run(svc.setup_repo_webhook(db_session, "badformat", "https://cb")) is None

    repo = _repo(db_session, "octocat/Hooked")
    post = AsyncMock(return_value=_resp({"id": 555}))
    monkeypatch.setattr("config.settings.github_token", "tok")
    with _patch_http(post=post):
        webhook = _run(svc.setup_repo_webhook(db_session, repo.full_name, "https://cb.example/hook"))
    assert webhook == {"id": 555}
    db_session.refresh(repo)
    assert repo.webhook_id == 555
    assert repo.webhook_secret  # plaintext read-back through EncryptedText

    # Repo absent from DB → webhook still created, nothing persisted.
    post2 = AsyncMock(return_value=_resp({"id": 556}))
    with _patch_http(post=post2):
        webhook2 = _run(svc.setup_repo_webhook(db_session, "octocat/Ghost", "https://cb"))
    assert webhook2 == {"id": 556}


def test_items_by_goal_and_repo(db_session):
    repo = _repo(db_session)
    other = _repo(db_session, "octocat/Other")
    goal = Goal(title="g")
    db_session.add(goal)
    db_session.flush()
    item = _item(db_session, repo.id, goal_id=goal.id, external_id=1)
    _item(db_session, repo.id, external_id=2)
    _item(db_session, other.id, external_id=3)

    assert [i.id for i in svc.get_items_by_goal(db_session, goal.id)] == [item.id]
    assert len(svc.get_items_by_repo(db_session, repo.id)) == 2
    assert len(svc.get_items_by_repo(db_session, other.id)) == 1
