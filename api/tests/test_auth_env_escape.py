"""Regression tests for #1456: AUTH_PASSWORD written to .env with
docker-compose ``$$`` escaping must authenticate as the underlying bcrypt
hash — the read path unescapes ``$$`` → ``$`` so file-consumed secrets see
their effective value.
"""

import sys
import types

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from fastapi.testclient import TestClient
from services.auth_service import hash_password
from services.env_file import get_persisted, read_env, unescape_env_value

_TEST_SECRET = "test-secret-key-for-env-escape"  # noqa: S105 — test fixture, not a real secret


def test_unescape_env_value():
    assert unescape_env_value("$$2b$$12$$abcDEFhash") == "$2b$12$abcDEFhash"
    assert unescape_env_value("plain") == "plain"
    assert unescape_env_value("") == ""
    # A lone "$" is not an escape pair — left untouched.
    assert unescape_env_value("$2b$hash") == "$2b$hash"


def test_get_persisted_unescapes_dollar_pairs(persisted_env):
    persisted_env.write_text("AUTH_PASSWORD=$$2b$$12$$abcDEFhash\nSECRET_KEY=s3$$cret\n")
    assert get_persisted("AUTH_PASSWORD") == "$2b$12$abcDEFhash"
    assert get_persisted("SECRET_KEY") == "s3$cret"


def test_read_env_stays_raw(persisted_env):
    """read_env feeds update_config's write_env round-trip: it must return
    the file verbatim or a settings save would silently rewrite every
    ``$$``-escaped entry (including keys compose *does* interpolate)."""
    persisted_env.write_text("AUTH_PASSWORD=$$2b$$12$$abcDEFhash\n")
    assert read_env()["AUTH_PASSWORD"] == "$$2b$$12$$abcDEFhash"


def test_login_with_escaped_bcrypt_succeeds(client: TestClient, persisted_env):
    """End-to-end #1456: stored ``$$``-escaped hash + real password → 200.

    The literal escaped string must NOT authenticate (that was the hole:
    the hash text itself became the password while the real one 401'd).
    """
    stored_hash = hash_password("s3cret")
    escaped = stored_hash.replace("$", "$$")
    persisted_env.write_text(f"AUTH_PASSWORD={escaped}\n")
    settings.secret_key = _TEST_SECRET
    settings.auth_password = ""

    assert client.post("/auth/login", json={"password": "s3cret"}).status_code == 200
    assert client.post("/auth/login", json={"password": escaped}).status_code == 401
    assert client.post("/auth/login", json={"password": stored_hash}).status_code == 401
