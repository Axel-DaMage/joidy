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

from database import Base, get_db
import main as main_module
from main import app
from fastapi.testclient import TestClient
from middleware.rate_limit import _default_limiter
from services.auth_service import get_current_user

_DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_POSTGRES = _DATABASE_URL.startswith("postgresql")

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
        Base.metadata.drop_all(engine)
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
