import sys
import types

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None
    sys.modules["sqlite_vec"] = _stub

from database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS tag_cooccurrences "
                "(tag_a_id INTEGER, tag_b_id INTEGER, weight INTEGER, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            ))
        except Exception:
            pass
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()
