"""Regression coverage for #1275: INTERNAL_API_TOKEN service auth.

The pass-the-hash shortcut let anyone holding the stored bcrypt
AUTH_PASSWORD authenticate as if they knew the plaintext. Services
(worker) now authenticate with a dedicated INTERNAL_API_TOKEN through
``get_current_user_or_internal``, and the stored hash is just a hash —
``POST /auth/login`` rejects it.
"""

from unittest.mock import patch

import pytest
from database import get_db
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from main import app
from services.auth_service import get_current_user_or_internal, hash_password
from starlette.requests import Request


def test_login_rejects_stored_hash(persisted_env):
    """POST /auth/login with the .env bcrypt hash must return 401 (#1275)."""
    stored = hash_password("s3cret")
    persisted_env.write_text(f"AUTH_PASSWORD={stored}\nSECRET_KEY=test-secret\n")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.post("/auth/login", json={"password": stored}).status_code == 401
        assert client.post("/auth/login", json={"password": "s3cret"}).status_code == 200


def test_internal_token_dependency(persisted_env):
    """The dedicated dependency accepts the service token, rejects the rest."""
    persisted_env.write_text("INTERNAL_API_TOKEN=service-tok\nAUTH_PASSWORD=x\n")

    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 50000)})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="service-tok")
    assert get_current_user_or_internal(request, creds) == 1

    bad = HTTPAuthorizationCredentials(scheme="Bearer", credentials="nope")
    with pytest.raises(HTTPException):
        get_current_user_or_internal(request, bad)


def test_internal_token_authenticates_vault_routes(persisted_env, db_session):
    """Service routes accept the token end-to-end; the stored hash does not."""
    stored = hash_password("s3cret")
    persisted_env.write_text(f"AUTH_PASSWORD={stored}\nINTERNAL_API_TOKEN=service-tok\n")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with (
            TestClient(app, client=("127.0.0.1", 50000)) as client,
            patch("routers.vault.write_daily", return_value=True),
        ):
            assert client.post("/vault/write-daily").status_code == 401
            assert client.post("/vault/write-daily", headers={"Authorization": "Bearer service-tok"}).status_code == 200
            assert client.post("/vault/write-daily", headers={"Authorization": f"Bearer {stored}"}).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
