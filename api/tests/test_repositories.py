"""Direct unit tests for the repository (data-access) layer.

``repositories.py`` wraps SQLAlchemy sessions with domain query methods used
by routers and services. Router tests only exercise the happy paths they need;
these tests pin each repository method's filtering, ordering and return shape
against a real database session (#1401).
"""

import repositories
from models.gamification import StreakRecord, XPEvent
from models.github import (
    GitHubItem,
    GitHubItemType,
    GitHubRepo,
)
from models.goal import Goal, GoalState, GoalTemporality
from models.note import Note, Tag
from models.personal_streaks import PersonalStreak, StreakCheckIn
from models.skill import Skill
from services.timezone_utils import get_local_today


def _note(db, title="Repo note", **kwargs) -> Note:
    note = Note(title=title, content=kwargs.pop("content", "body"), source="joidy", **kwargs)
    db.add(note)
    db.flush()
    return note


def _tag(db, name) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.flush()
    return tag


def _goal(db, title="Repo goal", **kwargs) -> Goal:
    goal = Goal(title=title, temporality=GoalTemporality.DAILY, **kwargs)
    db.add(goal)
    db.flush()
    return goal


# ─── BaseRepository generic CRUD ──────────────────────────────────────────────


def test_base_repository_crud(db_session):
    repo = repositories.BaseRepository(db_session, Note)
    note = _note(db_session, "crud-note")

    assert repo.get(note.id) is not None
    assert repo.get(999999) is None
    assert any(n.id == note.id for n in repo.list())
    assert repo.count() >= 1

    fetched = repo.get(note.id)
    repo.delete(fetched)
    db_session.flush()
    assert repo.get(note.id) is None


def test_base_repository_add_returns_refreshed(db_session):
    repo = repositories.BaseRepository(db_session, Tag)
    tag = repo.add(Tag(name="repo-add-tag"))
    assert tag.id is not None
    assert db_session.query(Tag).filter(Tag.name == "repo-add-tag").count() == 1


# ─── GoalRepository ───────────────────────────────────────────────────────────


def test_goal_repo_queries(db_session):
    repo = repositories.GoalRepository(db_session)
    active = _goal(db_session, "active-goal", state=GoalState.ACTIVE)
    _goal(db_session, "failed-goal", state=GoalState.FAILED)
    note = _note(db_session, "goal-note")
    linked = _goal(db_session, "linked-goal", note_id=note.id)

    assert {g.id for g in repo.get_active()} >= {active.id}
    assert {g.id for g in repo.get_by_note(note.id)} == {linked.id}


# ─── Gamification repositories ────────────────────────────────────────────────


def test_user_stats_repo_get_or_create(db_session):
    repo = repositories.UserStatsRepository(db_session)
    stats = repo.get_or_create()
    assert stats.id is not None
    again = repo.get_or_create()
    assert again.id == stats.id


def test_xp_event_repo_find_by_dedup_key(db_session):
    repo = repositories.XPEventRepository(db_session)
    event = XPEvent(event_type="goal_completed", xp=50, dedup_key="repo-new")
    db_session.add(event)
    db_session.flush()

    found = repo.find_by_dedup_key("goal_completed", "repo-new")
    assert found is not None and found.xp == 50
    assert repo.find_by_dedup_key("goal_completed", "missing") is None


def test_streak_record_repo_get_today(db_session):
    repo = repositories.StreakRecordRepository(db_session)
    today = get_local_today()
    record = StreakRecord(activity_date=today, xp_earned=15)
    db_session.add(record)
    db_session.flush()

    found = repo.get_today()
    assert found is not None
    assert found.activity_date == today


# ─── GitHub repositories ──────────────────────────────────────────────────────


def _github_repo(db, full_name="octo/repo") -> GitHubRepo:
    repo = GitHubRepo(
        name=full_name.split("/")[1],
        full_name=full_name,
        url=f"https://github.com/{full_name}",
    )
    db.add(repo)
    db.flush()
    return repo


def _github_item(db, repo_id, external_id=1, **kwargs) -> GitHubItem:
    item = GitHubItem(
        repo_id=repo_id,
        external_id=external_id,
        item_type=kwargs.pop("item_type", GitHubItemType.ISSUE),
        number=kwargs.pop("number", external_id),
        title=kwargs.pop("title", "item"),
        url="https://api.github.com/x",
        html_url="https://github.com/x",
        **kwargs,
    )
    db.add(item)
    db.flush()
    return item


def test_github_repo_repo_find_by_full_name(db_session):
    repo = repositories.GitHubRepoRepository(db_session)
    gh = _github_repo(db_session, "find/repo")
    assert repo.find_by_full_name("find/repo").id == gh.id
    assert repo.find_by_full_name("missing/repo") is None


def test_github_item_repo_get(db_session):
    repo = repositories.GitHubItemRepository(db_session)
    gh = _github_repo(db_session, "items/repo")
    item = _github_item(db_session, gh.id, external_id=42)

    assert repo.get(item.id).id == item.id
    assert repo.get(999999) is None


# ─── Skill / PersonalStreak / Config repositories ─────────────────────────────


def test_skill_repo_list_by_tag_ids(db_session):
    repo = repositories.SkillRepository(db_session)
    t1 = _tag(db_session, "skill-t1")
    t2 = _tag(db_session, "skill-t2")
    t3 = _tag(db_session, "skill-t3")
    s1 = Skill(tag_id=t1.id, note_count=5)
    s2 = Skill(tag_id=t2.id, note_count=2)
    s3 = Skill(tag_id=t3.id, note_count=1)
    db_session.add_all([s1, s2, s3])
    db_session.flush()

    found = repo.list_by_tag_ids({t1.id, t2.id})
    assert {s.id for s in found} == {s1.id, s2.id}
    assert repo.list_by_tag_ids(set()) == []


def test_streak_checkin_repo_crud(db_session):
    repo = repositories.StreakCheckInRepository(db_session)
    streak = PersonalStreak(name="ci-streak")
    db_session.add(streak)
    db_session.flush()
    ci = repo.add(StreakCheckIn(streak_id=streak.id, check_date=get_local_today()))
    assert ci.id is not None
    assert repo.count() >= 1


def test_config_repo(db_session):
    repo = repositories.ConfigRepository(db_session)
    repo.set("repo_key", "value1")
    repo.set("repo_key", "value2")  # update path
    repo.set("other_key", "other")
    db_session.flush()

    assert repo.get("repo_key") == "value2"
    assert repo.get("missing_key") is None
    all_cfg = repo.get_all_as_dict()
    assert all_cfg["repo_key"] == "value2"
    assert all_cfg["other_key"] == "other"
