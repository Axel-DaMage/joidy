"""Tests for the auth router (/auth/login, /auth/status).

Uses the FastAPI TestClient via the `client` fixture from conftest.py.
The auth router is excluded from JWT enforcement, so these endpoints are
reachable without a bearer token.
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
from services.auth_service import TOKEN_TYPE_REFRESH, hash_password, verify_token


def test_login_with_valid_credentials(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        response = client.post("/auth/login", json={"password": "s3cret"})
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert len(data["access_token"]) > 0
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_login_with_invalid_credentials(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        response = client.post("/auth/login", json={"password": "wrong"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_login_without_password_configured_succeeds(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = ""
        # No password configured → any password is accepted.
        response = client.post("/auth/login", json={"password": "anything"})
        assert response.status_code == 200
        assert "access_token" in response.json()
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_login_without_secret_key_returns_500(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = ""
        settings.auth_password = hash_password("s3cret")
        response = client.post("/auth/login", json={"password": "s3cret"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Server not configured for auth"
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_auth_status_when_configured(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        response = client.get("/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        # has_password must not be exposed (#647)
        assert "has_password" not in data
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_auth_status_when_not_configured(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = ""
        settings.auth_password = ""
        response = client.get("/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        # has_password must not be exposed (#647)
        assert "has_password" not in data
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_login_returns_valid_token(client: TestClient):
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        response = client.post("/auth/login", json={"password": "s3cret", "username": "alice"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        # The token should be verifiable with the same secret.
        from services.auth_service import get_current_user_id

        assert get_current_user_id(token) == 1
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_placeholder_secret_key_disables_auth(client: TestClient):
    """Regression for #1393: the .env.example placeholder must count as unset —
    /auth/status reports disabled and /auth/login refuses to issue a JWT."""
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "change_this_to_a_random_secret_key"
        settings.auth_password = hash_password("s3cret")
        status_response = client.get("/auth/status")
        assert status_response.status_code == 200
        assert status_response.json()["enabled"] is False
        response = client.post("/auth/login", json={"password": "s3cret"})
        assert response.status_code == 500
        assert "access_token" not in response.json()
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_login_rejects_query_param_credentials(client: TestClient):
    """Credentials must not be accepted via query params (#647)."""
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        # Sending password as a query param with no body → 422 (missing body)
        response = client.post("/auth/login?password=s3cret")
        assert response.status_code == 422
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_login_returns_refresh_token(client: TestClient):
    """Login returns an access + refresh token pair (#1285)."""
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        response = client.post("/auth/login", json={"password": "s3cret"})
        assert response.status_code == 200
        data = response.json()
        assert "refresh_token" in data
        # The refresh token must verify as typ=refresh, not access.
        payload = verify_token(data["refresh_token"], expected_type=TOKEN_TYPE_REFRESH)
        assert payload is not None
        assert payload["sub"] == "1"
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_refresh_returns_rotated_token_pair(client: TestClient):
    """POST /auth/refresh exchanges a refresh token for a new pair (#1285)."""
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        login = client.post("/auth/login", json={"password": "s3cret"}).json()

        response = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        # New access token verifies and authenticates as user 1.
        from services.auth_service import get_current_user_id

        assert get_current_user_id(data["access_token"]) == 1
        # Rotation: the new refresh token differs from the presented one.
        assert data["refresh_token"] != login["refresh_token"]
        assert verify_token(data["refresh_token"], expected_type=TOKEN_TYPE_REFRESH) is not None
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_refresh_rejects_access_token(client: TestClient):
    """An access token (typ=access) cannot be used as a refresh token."""
    orig_password = settings.auth_password
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        settings.auth_password = hash_password("s3cret")
        login = client.post("/auth/login", json={"password": "s3cret"}).json()

        response = client.post("/auth/refresh", json={"refresh_token": login["access_token"]})
        assert response.status_code == 401
    finally:
        settings.auth_password = orig_password
        settings.secret_key = orig_key


def test_refresh_rejects_garbage_token(client: TestClient):
    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        response = client.post("/auth/refresh", json={"refresh_token": "not.a.jwt"})
        assert response.status_code == 401
    finally:
        settings.secret_key = orig_key


def test_refresh_rejects_expired_refresh_token(client: TestClient):
    from datetime import UTC, datetime, timedelta

    import jwt
    from services.auth_service import ALGORITHM, AUDIENCE, ISSUER

    orig_key = settings.secret_key
    try:
        settings.secret_key = "test-secret-key-for-auth-router"
        expired = jwt.encode(
            {
                "sub": "1",
                "typ": TOKEN_TYPE_REFRESH,
                "iss": ISSUER,
                "aud": AUDIENCE,
                "iat": datetime.now(UTC) - timedelta(days=10),
                "exp": datetime.now(UTC) - timedelta(days=3),
            },
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        response = client.post("/auth/refresh", json={"refresh_token": expired})
        assert response.status_code == 401
    finally:
        settings.secret_key = orig_key
