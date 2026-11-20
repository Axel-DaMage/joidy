"""Tests for GitHub integration router (username mode, device flow, error handling)."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.github import GitHubEvent, GitHubRepo
from services import oauth_state
from sqlalchemy import delete


def test_github_status_unconfigured(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")

    resp = client.get("/integrations/github/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "username": None}


def test_github_status_token(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "fake-token")

    fake_response = MagicMock()
    fake_response.json.return_value = {"login": "octocat"}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/status")
        assert resp.status_code == 200
        assert resp.json() == {"connected": True, "username": "octocat"}


def test_github_status_username_only(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")

    fake_response = MagicMock()
    fake_response.json.return_value = {"login": "octocat"}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/status")
        assert resp.status_code == 200
        assert resp.json() == {"connected": True, "username": "octocat"}


def test_github_repos_username_only(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")

    fake_response = MagicMock()
    fake_response.json.return_value = [
        {
            "id": 1,
            "name": "Hello-World",
            "full_name": "octocat/Hello-World",
            "description": "My first repo",
            "private": False,
            "html_url": "https://github.com/octocat/Hello-World",
            "default_branch": "master",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/repos")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["repos"]) == 1
        assert data["repos"][0]["full_name"] == "octocat/Hello-World"
        assert "color" in data["repos"][0]


def test_github_device_flow_unconfigured(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "")

    resp = client.get("/integrations/github/oauth/device/start")
    assert resp.status_code == 400
    assert "GitHub OAuth not configured" in resp.json()["detail"]


def test_github_device_flow_start_success(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("config.settings.secret_key", "test-secret")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "device_code": "dev123",
        "user_code": "ABCD-1234",
        "verification_uri": "https://github.com/login/device",
        "expires_in": 900,
        "interval": 5,
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/oauth/device/start")
        assert resp.status_code == 200
        data = resp.json()
        # The raw device_code never leaves the server (#1318); the client
        # gets an opaque sealed handle to hand back to /oauth/device/polling.
        assert "device_code" not in data
        assert oauth_state.unseal_value("github-device", data["poll_token"]) == "dev123"
        assert data["user_code"] == "ABCD-1234"


def test_github_device_flow_polling_pending(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    poll_token = oauth_state.seal_value("github-device", "dev123")

    fake_response = MagicMock()
    fake_response.json.return_value = {"error": "authorization_pending"}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/integrations/github/oauth/device/polling", json={"poll_token": poll_token})
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"


def test_github_device_flow_polling_authorized(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "my-secret")
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    poll_token = oauth_state.seal_value("github-device", "dev123")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "gho_token123",
        "token_type": "bearer",
        "scope": "public_repo,read:user",
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/integrations/github/oauth/device/polling", json={"poll_token": poll_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "authorized"
        assert data["access_token"] == "gho_token123"


def test_github_device_flow_polling_rejects_query_secret(client, monkeypatch):
    """#1318: device_code must travel in the JSON body, never the query string."""
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post("/integrations/github/oauth/device/polling?device_code=dev123")

    assert resp.status_code == 422  # required body missing; query secret ignored
    post.assert_not_called()


def test_github_device_flow_polling_rejects_forged_poll_token(client, monkeypatch):
    """#1318: a poll_token not minted by /oauth/device/start cannot redeem codes."""
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("config.settings.secret_key", "test-secret")

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(
            "/integrations/github/oauth/device/polling",
            json={"poll_token": "forged.token.value"},
        )

    assert resp.status_code == 403
    post.assert_not_called()


def test_github_device_flow_polling_rejects_foreign_purpose_token(client, monkeypatch):
    """A seal minted for a different purpose must not unseal as a device code."""
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    foreign = oauth_state.seal_value("other-purpose", "dev123")

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post(
            "/integrations/github/oauth/device/polling",
            json={"poll_token": foreign},
        )

    assert resp.status_code == 403
    post.assert_not_called()


def test_github_oauth_revoke_token_in_body(client, monkeypatch):
    """#1318: revoke takes the token in the JSON body, not the query string."""
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "my-secret")

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None

    post = AsyncMock(return_value=fake_response)
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post("/integrations/github/oauth/revoke", json={"token": "tok_in_body"})

    assert resp.status_code == 200
    assert post.call_args.kwargs["data"]["access_token"] == "tok_in_body"


def test_github_oauth_revoke_ignores_query_token(client, monkeypatch):
    """A ?token= query param must not be honored — it leaks into access logs."""
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "my-secret")
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "configured-tok")

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None

    post = AsyncMock(return_value=fake_response)
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.post("/integrations/github/oauth/revoke?token=leaked-in-url")

    assert resp.status_code == 200
    # Falls back to the configured token; the query-string value is unused.
    assert post.call_args.kwargs["data"]["access_token"] == "configured-tok"


def test_github_oauth_scopes_least_privilege(client):
    """#1318: no "repo" (full private control) or "workflow" (Actions) grants."""
    resp = client.get("/integrations/github/oauth/scopes")
    assert resp.status_code == 200
    scopes = resp.json()["scopes"]
    assert "repo" not in scopes
    assert "workflow" not in scopes


def test_github_owner_repo_param_validation(client):
    """#1318: owner/repo path params are validated before URL interpolation."""
    resp = client.get("/integrations/github/repos/bad%20name/repo")
    assert resp.status_code == 400

    resp = client.get("/integrations/github/repos/owner/bad%3Fname")
    assert resp.status_code == 400

    resp = client.post("/integrations/github/repos/db", params={"full_name": "../x"})
    assert resp.status_code == 400

    resp = client.post("/integrations/github/repos/db", params={"full_name": "a%3Fb/c"})
    assert resp.status_code == 400


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _webhook_payload(full_name: str = "octocat/Hello-World") -> bytes:
    return json.dumps(
        {
            "action": "opened",
            "repository": {"full_name": full_name},
            "sender": {"login": "octocat"},
            "issue": {"number": 1, "id": 99},
        }
    ).encode()


@pytest.fixture
def tracked_repo(db_session):
    """A repo row with a per-repo webhook secret, purged at teardown.

    The webhook endpoint's ``record_event`` commits mid-request, and under
    the SQLite StaticPool test engine those commits outlive the fixture
    rollback — so residue is deleted explicitly to keep tests isolated.
    """
    repo = GitHubRepo(
        name="Hello-World",
        full_name="octocat/Hello-World",
        url="https://github.com/octocat/Hello-World",
        webhook_id=1,
        webhook_secret="hook-secret",
    )
    db_session.add(repo)
    db_session.flush()
    yield repo
    # The endpoint's record_event commits inside the ASGI portal thread, which
    # durably commits under the SQLite StaticPool test engine; a session-level
    # delete+commit here only releases a savepoint that the outer rollback
    # then discards. Cleaning up at the Connection level survives both.
    db_session.rollback()
    bind = db_session.get_bind()
    bind.execute(delete(GitHubEvent))
    bind.execute(delete(GitHubRepo))
    bind.commit()


def test_webhook_rejects_missing_signature(client, tracked_repo):
    resp = client.post(
        "/integrations/github/webhook",
        content=_webhook_payload(),
        headers={"X-GitHub-Event": "issues"},
    )
    assert resp.status_code == 401


def test_webhook_rejects_forged_signature(client, tracked_repo):
    body = _webhook_payload()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign("wrong-secret", body),
        },
    )
    assert resp.status_code == 401


def test_webhook_fails_closed_without_secret(client, db_session, monkeypatch):
    """#1318: no per-repo secret and no GITHUB_WEBHOOK_SECRET → deny, don't process."""
    monkeypatch.setattr("routers.integrations.github.settings.github_webhook_secret", "")
    body = _webhook_payload()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign("anything", body),
        },
    )
    assert resp.status_code == 401


def test_webhook_accepts_valid_signature(client, tracked_repo):
    body = _webhook_payload()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign("hook-secret", body),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"
    assert resp.json()["event_id"] is not None


def test_webhook_global_secret_fallback(client, monkeypatch):
    """Untracked repos verify against the global GITHUB_WEBHOOK_SECRET."""
    monkeypatch.setattr("routers.integrations.github.settings.github_webhook_secret", "global-secret")
    body = _webhook_payload(full_name="ghost/NotTracked")
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign("global-secret", body),
        },
    )
    assert resp.status_code == 200


def test_webhook_ignores_unknown_event_type(client, tracked_repo):
    """Signed-but-untracked event types (e.g. ping) are acknowledged, not stored."""
    body = _webhook_payload()
    resp = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _sign("hook-secret", body),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def _configure_github_web_flow(monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "my-secret")
    monkeypatch.setattr(
        "routers.integrations.github.settings.github_oauth_web_url",
        "http://localhost:8000/integrations/github/oauth/callback",
    )
    monkeypatch.setattr("config.settings.secret_key", "test-secret")


def test_github_web_flow_start_includes_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)

    resp = client.get("/integrations/github/oauth/web/start")
    assert resp.status_code == 200
    data = resp.json()
    # CSRF nonce must be embedded so GitHub echoes it back to /callback (#1280).
    assert f"state={data['state']}" in data["authorize_url"]
    assert oauth_state.verify_state(data["state"], "github") is True


def test_github_oauth_callback_rejects_missing_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get("/integrations/github/oauth/callback?code=abc123")

    assert resp.status_code == 403
    post.assert_not_called()  # denied before any token exchange


def test_github_oauth_callback_rejects_wrong_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get("/integrations/github/oauth/callback?code=abc123&state=forged")

    assert resp.status_code == 403
    post.assert_not_called()


def test_github_oauth_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for Google must not pass at GitHub's callback.
    _configure_github_web_flow(monkeypatch)
    state = oauth_state.generate_state("google")

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"/integrations/github/oauth/callback?code=abc123&state={state}")

    assert resp.status_code == 403
    post.assert_not_called()


def test_github_oauth_callback_valid_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)
    state = oauth_state.generate_state("github")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "gho_token123",
        "token_type": "bearer",
        "scope": "repo,read:user",
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/github/oauth/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "authorized"
