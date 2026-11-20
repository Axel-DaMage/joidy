"""Direct unit tests for the repository (data-access) layer.

``repositories.py`` wraps SQLAlchemy sessions with domain query methods used
by routers and services. Router tests only exercise the happy paths they need;
these tests pin each repository method's filtering, ordering and return shape
against a real database session (#1401).
"""

from datetime import UTC, datetime, timedelta

import repositories
from models.gamification import StreakRecord, XPEvent
from models.github import (
    GitHubEvent,
    GitHubEventType,
    GitHubItem,
    GitHubItemType,
    GitHubRepo,
)
from models.goal import Goal, GoalState, GoalTemporality
from models.note import EmbeddingFailure, Note, NoteLink, NoteTag, Tag, TagCooccurrence
from models.personal_streaks import PersonalStreak, StreakCheckIn
from models.planning import PlanningAssignment
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


# ─── NoteRepository ───────────────────────────────────────────────────────────


def test_note_repo_find_by_path(db_session):
    repo = repositories.NoteRepository(db_session)
    _note(db_session, "with-path", source_path="vault/a.md")
    _note(db_session, "other")

    found = repo.find_by_path("vault/a.md")
    assert found is not None
    assert found.title == "with-path"
    assert repo.find_by_path("vault/missing.md") is None


def test_note_repo_find_by_tag(db_session):
    repo = repositories.NoteRepository(db_session)
    tag = _tag(db_session, "repo-tag")
    tagged = _note(db_session, "tagged-note")
    _note(db_session, "untagged-note")
    db_session.add(NoteTag(note_id=tagged.id, tag_id=tag.id))
    db_session.flush()

    results = repo.find_by_tag(tag.id)
    assert [n.id for n in results] == [tagged.id]


def test_note_repo_search(db_session):
    repo = repositories.NoteRepository(db_session)
    _note(db_session, "UniqueTitleXYZ", content="nothing")
    _note(db_session, "plain", content="contains uniquetitlexyz in body")
    _note(db_session, "plain2", content="unrelated")

    results = repo.search("uniquetitlexyz")
    assert len(results) == 2
    limited = repo.search("uniquetitlexyz", limit=1)
    assert len(limited) == 1


def test_note_repo_get_orphaned(db_session):
    repo = repositories.NoteRepository(db_session)
    tagged = _note(db_session, "has-tag")
    orphan = _note(db_session, "orphan")
    tag = _tag(db_session, "orphan-tag")
    db_session.add(NoteTag(note_id=tagged.id, tag_id=tag.id))
    db_session.flush()

    orphans = repo.get_orphaned()
    orphan_ids = {n.id for n in orphans}
    assert orphan.id in orphan_ids
    assert tagged.id not in orphan_ids


def test_note_repo_get_recent(db_session):
    repo = repositories.NoteRepository(db_session)
    recent = _note(db_session, "recent-note")
    old = _note(db_session, "old-note")
    old.created_at = datetime.now(UTC) - timedelta(days=30)
    db_session.flush()

    results = repo.get_recent(days=7)
    ids = {n.id for n in results}
    assert recent.id in ids
    assert old.id not in ids


def test_note_repo_get_created_between(db_session):
    repo = repositories.NoteRepository(db_session)
    n1 = _note(db_session, "in-window")
    n2 = _note(db_session, "out-window")
    n2.created_at = datetime.now(UTC) - timedelta(days=10)
    db_session.flush()

    start = datetime.now(UTC) - timedelta(days=2)
    end = datetime.now(UTC) + timedelta(days=1)
    results = repo.get_created_between(start, end)
    ids = {n.id for n in results}
    assert n1.id in ids
    assert n2.id not in ids


# ─── Tag / NoteTag / NoteLink / TagCooccurrence ───────────────────────────────


def test_tag_repo_find_by_name(db_session):
    repo = repositories.TagRepository(db_session)
    tag = _tag(db_session, "find-me-tag")
    assert repo.find_by_name("find-me-tag").id == tag.id
    assert repo.find_by_name("nope") is None


def test_note_tag_repo_crud(db_session):
    repo = repositories.NoteTagRepository(db_session)
    note = _note(db_session)
    tag = _tag(db_session, "nt-tag")
    nt = repo.add(NoteTag(note_id=note.id, tag_id=tag.id))
    assert nt.note_id == note.id
    assert repo.count() >= 1


def test_note_link_repo(db_session):
    repo = repositories.NoteLinkRepository(db_session)
    a = _note(db_session, "link-a")
    b = _note(db_session, "link-b")
    link = NoteLink(source_note_id=a.id, target_note_id=b.id)
    db_session.add(link)
    db_session.flush()

    by_source = repo.find_by_source(a.id)
    assert len(by_source) == 1
    assert by_source[0].target_note_id == b.id

    repo.delete_for_note(a.id)
    db_session.flush()
    assert repo.find_by_source(a.id) == []


def test_tag_cooccurrence_repo(db_session):
    repo = repositories.TagCooccurrenceRepository(db_session)
    t1 = _tag(db_session, "co-t1")
    t2 = _tag(db_session, "co-t2")
    db_session.add(TagCooccurrence(tag_a_id=t1.id, tag_b_id=t2.id, weight=5))
    db_session.flush()

    graph = repo.get_graph_data()
    assert any(r.tag_a_id == t1.id and r.tag_b_id == t2.id for r in graph)

    repo.delete_for_tags({t1.id})
    db_session.flush()
    assert repo.get_graph_data() == [] or all(
        r.tag_a_id != t1.id and r.tag_b_id != t1.id for r in repo.get_graph_data()
    )


# ─── EmbeddingFailureRepository ───────────────────────────────────────────────


def test_embedding_failure_repo(db_session):
    repo = repositories.EmbeddingFailureRepository(db_session)
    note = _note(db_session, "embed-note")

    retryable = EmbeddingFailure(note_id=note.id, attempts=1, last_error="boom")
    dead = _note(db_session, "dead-note")
    dead_failure = EmbeddingFailure(note_id=dead.id, attempts=99, last_error="dead")
    future = _note(db_session, "future-note")
    future_failure = EmbeddingFailure(
        note_id=future.id,
        attempts=1,
        last_error="later",
        next_retry_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add_all([retryable, dead_failure, future_failure])
    db_session.flush()

    assert repo.find_by_note(note.id).note_id == note.id
    assert repo.find_by_note(999999) is None

    retryable_ids = {f.note_id for f in repo.get_retryable()}
    assert note.id in retryable_ids
    assert dead.id not in retryable_ids  # attempts >= max
    assert future.id not in retryable_ids  # next_retry_at in the future

    dead_ids = {f.note_id for f in repo.get_dead_letters()}
    assert dead.id in dead_ids
    assert repo.count_dead_letters() >= 1


# ─── GoalRepository ───────────────────────────────────────────────────────────


def test_goal_repo_queries(db_session):
    repo = repositories.GoalRepository(db_session)
    active = _goal(db_session, "active-goal", state=GoalState.ACTIVE)
    failed = _goal(db_session, "failed-goal", state=GoalState.FAILED)
    completed = _goal(
        db_session,
        "completed-goal",
        state=GoalState.COMPLETED,
        completed_at=datetime.now(UTC),
    )
    note = _note(db_session, "goal-note")
    linked = _goal(db_session, "linked-goal", note_id=note.id)

    assert {g.id for g in repo.get_active()} >= {active.id}
    assert failed.id in {g.id for g in repo.get_failed()}
    assert {g.id for g in repo.get_by_note(note.id)} == {linked.id}
    since = datetime.now(UTC) - timedelta(days=1)
    assert completed.id in {g.id for g in repo.get_completed_since(since)}
    old_since = datetime.now(UTC) + timedelta(days=1)
    assert completed.id not in {g.id for g in repo.get_completed_since(old_since)}


# ─── Gamification repositories ────────────────────────────────────────────────


def test_user_stats_repo_get_or_create(db_session):
    repo = repositories.UserStatsRepository(db_session)
    stats = repo.get_or_create()
    assert stats.id is not None
    again = repo.get_or_create()
    assert again.id == stats.id


def test_xp_event_repo(db_session):
    repo = repositories.XPEventRepository(db_session)
    old = XPEvent(event_type="note_created", xp=10, dedup_key="repo-old")
    old.created_at = datetime.now(UTC) - timedelta(days=10)
    new = XPEvent(event_type="goal_completed", xp=50, dedup_key="repo-new")
    db_session.add_all([old, new])
    db_session.flush()

    recent = repo.get_recent(limit=10)
    assert any(e.dedup_key == "repo-new" for e in recent)

    since = datetime.now(UTC) - timedelta(days=1)
    assert repo.count_since(since) >= 1
    assert repo.count_since(datetime.now(UTC) + timedelta(days=1)) == 0

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


def test_github_item_repo(db_session):
    repo = repositories.GitHubItemRepository(db_session)
    gh = _github_repo(db_session, "items/repo")
    item = _github_item(db_session, gh.id, external_id=42)

    assert repo.find_by_external_id(42).id == item.id
    assert repo.find_by_external_id(999) is None
    assert [i.id for i in repo.list_by_repo(gh.id)] == [item.id]
    assert repo.list_by_repo(999999) == []


def test_github_event_repo_list_by_repo(db_session):
    repo = repositories.GitHubEventRepository(db_session)
    gh = _github_repo(db_session, "events/repo")
    other = _github_repo(db_session, "other/repo")
    e1 = GitHubEvent(repo_id=gh.id, event_type=GitHubEventType.ISSUES, action="opened", sender="octo", payload={})
    e2 = GitHubEvent(repo_id=other.id, event_type=GitHubEventType.PUSH, action="push", sender="octo", payload={})
    db_session.add_all([e1, e2])
    db_session.flush()

    events = repo.list_by_repo(gh.id)
    assert len(events) == 1
    assert events[0].repo_id == gh.id
    assert repo.list_by_repo(999999) == []


# ─── Skill / PersonalStreak / Config / Planning repositories ──────────────────


def test_skill_repo(db_session):
    repo = repositories.SkillRepository(db_session)
    root_tag = _tag(db_session, "skill-root")
    child_tag = _tag(db_session, "skill-child")
    child_tag.parent_id = root_tag.id
    root_skill = Skill(tag_id=root_tag.id, note_count=5)
    child_skill = Skill(tag_id=child_tag.id, note_count=2)
    db_session.add_all([root_skill, child_skill])
    db_session.flush()

    assert repo.find_by_name("skill-root").id == root_skill.id
    assert repo.find_by_name("missing") is None
    root_ids = {s.id for s in repo.find_roots()}
    assert root_skill.id in root_ids
    # A skill whose tag has a parent is not a tree root.
    assert child_skill.id not in root_ids


def test_personal_streak_repo_get_active(db_session):
    repo = repositories.PersonalStreakRepository(db_session)
    active = PersonalStreak(name="repo-active-streak")
    archived = PersonalStreak(name="repo-archived-streak", is_archived=True)
    db_session.add_all([active, archived])
    db_session.flush()

    ids = {s.id for s in repo.get_active()}
    assert active.id in ids
    assert archived.id not in ids


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


def test_planning_assignment_repo_crud(db_session):
    repo = repositories.PlanningAssignmentRepository(db_session)
    goal = _goal(db_session, "planned-goal")
    pa = repo.add(PlanningAssignment(date=get_local_today(), goal_id=goal.id))
    assert pa.id is not None
    assert repo.get(pa.id).goal_id == goal.id


# ─── FastAPI DI providers ─────────────────────────────────────────────────────


def test_di_providers_return_repositories(db_session):
    """Each ``get_*_repo`` provider builds the right repository for the session."""
    assert isinstance(repositories.get_note_repo(db_session), repositories.NoteRepository)
    assert isinstance(repositories.get_tag_repo(db_session), repositories.TagRepository)
    assert isinstance(repositories.get_note_tag_repo(db_session), repositories.NoteTagRepository)
    assert isinstance(repositories.get_note_link_repo(db_session), repositories.NoteLinkRepository)
    assert isinstance(repositories.get_tag_cooccurrence_repo(db_session), repositories.TagCooccurrenceRepository)
    assert isinstance(repositories.get_embedding_failure_repo(db_session), repositories.EmbeddingFailureRepository)
    assert isinstance(repositories.get_goal_repo(db_session), repositories.GoalRepository)
    assert isinstance(repositories.get_planning_assignment_repo(db_session), repositories.PlanningAssignmentRepository)
    assert isinstance(repositories.get_user_stats_repo(db_session), repositories.UserStatsRepository)
    assert isinstance(repositories.get_xp_event_repo(db_session), repositories.XPEventRepository)
    assert isinstance(repositories.get_streak_record_repo(db_session), repositories.StreakRecordRepository)
    assert isinstance(repositories.get_github_repo_repo(db_session), repositories.GitHubRepoRepository)
    assert isinstance(repositories.get_github_item_repo(db_session), repositories.GitHubItemRepository)
    assert isinstance(repositories.get_github_event_repo(db_session), repositories.GitHubEventRepository)
    assert isinstance(repositories.get_skill_repo(db_session), repositories.SkillRepository)
    assert isinstance(repositories.get_personal_streak_repo(db_session), repositories.PersonalStreakRepository)
    assert isinstance(repositories.get_streak_checkin_repo(db_session), repositories.StreakCheckInRepository)
    assert isinstance(repositories.get_config_repo(db_session), repositories.ConfigRepository)
