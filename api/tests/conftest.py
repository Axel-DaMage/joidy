import os
import sys
import tempfile
import types
import warnings
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# sqlite_vec is only needed for the local SQLite fallback. Stub it before
# importing app modules so pgvector's Vector type doesn't blow up on SQLite.
# In CI we run against real PostgreSQL + pgvector (see .github/workflows/ci.yml,
# #409), so this stub is a no-op there.
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

# Hermeticity against a populated .env (#991): services.env_file re-reads the
# deployment's .env from disk on every get_persisted()/read_env() call, and
# auth_service._effective_auth_password()/_effective_secret_key() consult it
# before env vars — so a developer's real .env (AUTH_PASSWORD, SECRET_KEY,
# OBSIDIAN_WEBHOOK_SECRET) used to leak into the suite where fixtures could not
# override it. Point JOIDY_ENV_FILE at an isolated empty file BEFORE importing
# app modules: config.Settings reads it at import time and env_file resolves it
# dynamically on every call. Tests that need persisted values opt in via the
# `persisted_env` fixture below.
_TEST_ENV_FILE = Path(tempfile.mkdtemp(prefix="joidy-test-env-")) / ".env"
_TEST_ENV_FILE.write_text("")
os.environ["JOIDY_ENV_FILE"] = str(_TEST_ENV_FILE)

# Mark every test process as APP_ENV=test BEFORE any app module (config,
# main, ...) is imported. Forced (not setdefault) and placed above every
# other import on purpose: the dev compose overlay exports APP_ENV=development
# and `docker compose run` passes service env down, which used to win over
# setdefault — Settings() was then constructed with app_env="development" and
# the lifespan's vault auto-restore (#1158) seeded REAL goals from the
# mounted /vault into the test DB, failing test_list_goals_empty and
# test_get_system_stats locally while CI (which exports APP_ENV=test)
# stayed green.
os.environ["APP_ENV"] = "test"

# Test-only bcrypt cost (#996). Hash strength is irrelevant under test and
# passlib's default (12 rounds) made auth tests the slowest single test in the
# suite. Must be set before app modules import `config.settings`, which reads
# BCRYPT_ROUNDS once at Settings construction time. Overridable by exporting
# BCRYPT_ROUNDS explicitly.
os.environ.setdefault("BCRYPT_ROUNDS", "4")

# Safety: only allow destructive TRUNCATE on databases whose name contains
# "test" to prevent accidentally wiping a shared dev/production database (#503).
from urllib.parse import urlparse, urlunparse

_DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_POSTGRES = _DATABASE_URL.startswith("postgresql")
_DB_NAME = urlparse(_DATABASE_URL).path.lstrip("/") if _USE_POSTGRES else ""

# pytest-xdist sets PYTEST_XDIST_WORKER ("gw0", "gw1", ...) inside each worker
# process; it is unset for the controller and for non-xdist runs.
_WORKER_ID = os.getenv("PYTEST_XDIST_WORKER", "")


def _ensure_database(admin_url: str, db_name: str) -> str:
    """Create ``db_name`` on the server if missing; return a URL pointing at it.

    CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT. We
    connect to the database already present in ``admin_url`` purely as an
    entry point to the server.
    """
    parsed = urlparse(admin_url)
    new_url = urlunparse(parsed._replace(path=f"/{db_name}"))
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}).scalar()
            if not exists:
                try:
                    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                except Exception:
                    # Tolerate a concurrent CREATE DATABASE raced by another
                    # pytest process; only re-raise if the DB still isn't there.
                    exists = conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": db_name},
                    ).scalar()
                    if not exists:
                        raise
    finally:
        admin_engine.dispose()
    return new_url


# Must run before importing app modules: database.py builds its engine from
# settings.database_url at import time, so redirecting afterwards would leave
# every SessionLocal() (background tasks, services) pointed at the live DB.
#
# Two derivations from the incoming DATABASE_URL (#996):
# 1. If it doesn't name a test database, redirect to a sibling ``<db>_test``
#    database (created on demand) so isolation holds for `make test-api`,
#    `docker compose run` and bare `pytest` alike — without this the #503
#    guard below refuses to wipe, leaving tests both failing on accumulated
#    state and writing fixtures into real user data (#626).
# 2. Under pytest-xdist each worker gets its own database
#    (``joidy_test_gw0``, ``joidy_test_gw1``, ...) so `-n auto` runs in
#    parallel without workers truncating each other's tables.
if _USE_POSTGRES and _DB_NAME:
    _target_db = _DB_NAME if "test" in _DB_NAME.lower() else f"{_DB_NAME}_test"
    if _WORKER_ID:
        _target_db = f"{_target_db}_{_WORKER_ID}"
    if _target_db != _DB_NAME:
        _DATABASE_URL = _ensure_database(_DATABASE_URL, _target_db)
        _DB_NAME = _target_db
        os.environ["DATABASE_URL"] = _DATABASE_URL

_CAN_DROP = "test" in _DB_NAME.lower() if _DB_NAME else False

import main as main_module
from database import Base, get_db
from fastapi.testclient import TestClient
from main import app
from middleware.rate_limit import _default_limiter
from services.auth_service import get_current_user

# Prevent the app lifespan from running Alembic migrations during tests. The
# test fixture creates the schema directly via Base.metadata.create_all(), and
# running migrations on the same DB would conflict (table-already-exists) and
# pull in migration history that isn't relevant to unit/e2e tests.
main_module.init_db = lambda: None


def _wipe_all_tables(engine) -> None:
    """Delete all rows while keeping the schema (cheap drop_all replacement).

    Guards the same accumulated-state protections the old per-test
    drop_all provided (#626): catches writes that escape the per-test
    transaction — ``SessionLocal`` background-task paths, ``real_commit``
    tests, or residue from an aborted previous run.
    """
    if not _CAN_DROP:
        warnings.warn(
            f"Skipping table wipe for non-test database '{_DB_NAME}'. "
            "Use a database with 'test' in the name for test isolation.",
            RuntimeWarning,
            stacklevel=2,
        )
        return
    if _USE_POSTGRES:
        names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        if names:
            with engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    else:
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


def _has_committed_rows(engine) -> bool:
    """True if any table holds committed (i.e. leaked-out-of-transaction) rows.

    ``EXISTS (...) LIMIT 1`` short-circuits on the first non-empty table, so
    the probe costs ~1ms when the suite is clean — unlike a blanket TRUNCATE,
    which takes ~0.5s on all 24 tables and would reintroduce the per-test
    fixture tax (#996).
    """
    clauses = " OR ".join(f'EXISTS (SELECT 1 FROM "{t.name}" LIMIT 1)' for t in Base.metadata.sorted_tables)
    if not clauses:
        return False
    with engine.connect() as conn:
        return bool(conn.execute(text(f"SELECT {clauses}")).scalar())


@pytest.fixture(scope="session")
def _db_engine():
    """Session-scoped engine with the schema created exactly once.

    The previous fixture ran ``Base.metadata.drop_all``/``create_all`` per
    test — ~1.1s of DDL against PostgreSQL for every single test, the
    dominant cost of the suite (#996). The schema is identical for all tests,
    so it is built once here; per-test isolation comes from ``db_session``
    rolling back a SAVEPOINT-scoped transaction instead.

    In CI (DATABASE_URL=postgresql://...) this runs against a real PostgreSQL
    instance with pgvector, so tests catch PG-specific bugs (#409) — the
    SQLite fallback previously masked issues like #398/#399/#400. Locally,
    when no DATABASE_URL is set, it falls back to an in-memory SQLite DB.
    """
    import models  # noqa: F401

    if _USE_POSTGRES:
        engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        if _CAN_DROP:
            # A test DB persisted in a volume keeps tables from an older
            # model state; create_all never alters existing tables, so any
            # schema-changing merge would fail the whole suite with
            # UndefinedColumn errors (#1158). Rebuild once per session — the
            # per-test SAVEPOINT isolation of #996 is unaffected.
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        # A crashed earlier run may have left committed rows behind; start
        # the session from a clean slate (probe is ~1ms on empty tables).
        if _has_committed_rows(engine):
            _wipe_all_tables(engine)
    else:
        # SQLAlchemy 2.1+ requires StaticPool's `creator`; use poolclass so
        # create_engine injects the dialect creator itself.
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(request, _db_engine):
    """Per-test isolated session via a SAVEPOINT-wrapped outer transaction.

    The test runs inside a real transaction that is rolled back at teardown;
    the session joins it with ``join_transaction_mode="create_savepoint"`` so
    ``commit()``/``rollback()`` calls inside tested code release/roll back a
    SAVEPOINT instead of touching the outer transaction — app code that
    commits still works, and nothing persists past the test (#996).

    Tests that genuinely need commits visible to other connections can opt
    out with ``@pytest.mark.real_commit``: they get a plain engine-bound
    session and a full table wipe on teardown.
    """
    _clear_app_caches()
    if request.node.get_closest_marker("real_commit"):
        session = sessionmaker(bind=_db_engine)()
        try:
            yield session
        finally:
            session.close()
            _wipe_all_tables(_db_engine)
            _clear_app_caches()
        return

    conn = _db_engine.connect()
    outer_txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if outer_txn.is_active:
            outer_txn.rollback()
        conn.close()
        # Rollback already reverts everything the fixture session wrote; only
        # pay for a table wipe when writes escaped the transaction (SessionLocal
        # background paths) or an earlier run left committed residue.
        if _CAN_DROP and _has_committed_rows(_db_engine):
            _wipe_all_tables(_db_engine)
        _clear_app_caches()


def _clear_app_caches() -> None:
    """Drop in-process TTL caches between tests (issue #1099 follow-up).

    ``services.response_cache`` caches live for the lifetime of the pytest
    *process* and are NOT invalidated by the per-test savepoint rollback:
    e.g. ``GET /tags/`` decorates the list with ``@ttl_cache``, so a note
    (and tag) created by an earlier test in the same worker surfaced in a
    later ``test_list_tags_empty`` depending on xdist shard order — a
    phantom committed row that never left the DB.
    """
    try:
        from services.response_cache import clear_api_caches

        clear_api_caches()
    except Exception:
        pass


@pytest.fixture(autouse=True, scope="session")
def _disable_rate_limits():
    _default_limiter.requests_per_minute = 10_000
    _default_limiter.auth_requests_per_minute = 10_000


@pytest.fixture(autouse=True)
def _isolated_env_file(tmp_path, monkeypatch):
    """Give every test its own empty persisted .env (#991).

    Complements the session-level JOIDY_ENV_FILE above: even if a test (or an
    endpoint under test) writes through write_env(), the values land in a
    per-test tmp file and cannot leak into other tests.
    """
    env_path = tmp_path / "joidy.env"
    env_path.write_text("")
    monkeypatch.setenv("JOIDY_ENV_FILE", str(env_path))
    return env_path


@pytest.fixture
def persisted_env(_isolated_env_file):
    """Opt-in access to the test's persisted .env file.

    Tests that exercise get_persisted()/read_env()/write_env() behaviour seed
    values by writing ``KEY=value`` lines to the returned Path (or by calling
    write_env(), which resolves the same file). Nothing reads the deployment's
    real .env (#991).
    """
    return _isolated_env_file


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return 1  # Fake user ID for tests

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


@pytest.fixture
def client_no_auth():
    def override_get_current_user():
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)
