import os
import sys
import types

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# sqlite_vec is only needed for the local SQLite fallback. Stub it before
# importing app modules so pgvector's Vector type doesn't blow up on SQLite.
# In CI we run against real PostgreSQL + pgvector (see .github/workflows/ci.yml,
# #409), so this stub is a no-op there.
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

# Safety: only allow destructive drop_all on databases whose name contains
# "test" to prevent accidentally wiping a shared dev/production database (#503).
from urllib.parse import urlparse, urlunparse

_DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_POSTGRES = _DATABASE_URL.startswith("postgresql")
_DB_NAME = urlparse(_DATABASE_URL).path.lstrip("/") if _USE_POSTGRES else ""


def _redirect_to_test_database(url: str, db_name: str) -> tuple[str, str]:
    """Point the suite at a dedicated ``<db_name>_test`` database.

    ``make test-api`` runs inside the api container, which inherits
    DATABASE_URL for the live development database. The #503 guard below then
    refuses to drop_all, leaving tests with no isolation: they both fail on
    accumulated state and write fixtures into real user data (#626).

    Rather than depending on every caller to export the right DATABASE_URL,
    redirect to a sibling test database (created on demand) so isolation holds
    for `make test-api`, `docker compose run` and bare `pytest` alike.
    """
    parsed = urlparse(url)
    test_db = f"{db_name}_test"
    test_url = urlunparse(parsed._replace(path=f"/{test_db}"))

    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT. We
    # connect to the original database purely as an entry point to the server.
    admin_engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_db}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    finally:
        admin_engine.dispose()

    return test_url, test_db


# Must run before importing app modules: database.py builds its engine from
# settings.database_url at import time, so redirecting afterwards would leave
# every SessionLocal() (background tasks, services) pointed at the live DB.
if _USE_POSTGRES and _DB_NAME and "test" not in _DB_NAME.lower():
    _DATABASE_URL, _DB_NAME = _redirect_to_test_database(_DATABASE_URL, _DB_NAME)
    os.environ["DATABASE_URL"] = _DATABASE_URL

_CAN_DROP = "test" in _DB_NAME.lower() if _DB_NAME else False

from database import Base, get_db
import main as main_module
from main import app
from fastapi.testclient import TestClient
from middleware.rate_limit import _default_limiter
from services.auth_service import get_current_user

# Prevent the app lifespan from running Alembic migrations during tests. The
# test fixture creates the schema directly via Base.metadata.create_all(), and
# running migrations on the same DB would conflict (table-already-exists) and
# pull in migration history that isn't relevant to unit/e2e tests.
main_module.init_db = lambda: None


@pytest.fixture
def db_session():
    """Per-test isolated database session.

    In CI (DATABASE_URL=postgresql://...) this runs against a real PostgreSQL
    instance with pgvector, so tests catch PG-specific bugs (#409) — the
    SQLite fallback previously masked issues like #398/#399/#400. Locally,
    when no DATABASE_URL is set, it falls back to an in-memory SQLite DB.
    """
    if _USE_POSTGRES:
        engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(engine)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            pool=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool(),
        )
        Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()

    if _USE_POSTGRES:
        # Drop and recreate per test for isolation on PostgreSQL.
        # Guard: only drop on test databases to protect dev/prod (#503).
        if _CAN_DROP:
            Base.metadata.drop_all(engine)
        else:
            import warnings

            warnings.warn(
                f"Skipping drop_all for non-test database '{_DB_NAME}'. "
                "Use a database with 'test' in the name for test isolation.",
                RuntimeWarning,
                stacklevel=2,
            )
    engine.dispose()


@pytest.fixture(autouse=True, scope="session")
def _disable_rate_limits():
    _default_limiter.requests_per_minute = 10_000
    _default_limiter.auth_requests_per_minute = 10_000


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
