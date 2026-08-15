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
from services.auth_service import hash_password


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
