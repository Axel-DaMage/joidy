"""Coverage for ``services/github_service.py`` (#1401).

The service only retains webhook-event recording — the dead API client
wrappers and unused DB helpers were removed in #1527. These tests pin
``record_event`` and ``process_webhook_event``.
"""

from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItemType,
    GitHubRepo,
)
from services import github_service as svc


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
