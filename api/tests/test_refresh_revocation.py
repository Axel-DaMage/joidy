"""Tests for #1457: refresh-token rotation with server-side revocation.

Covers the ``refresh_tokens`` registry: happy-path rotation, replay of a
consumed jti (reuse detection → family revocation), ``/auth/logout``
invalidation, unknown-jti rejection, and the lazy expiry sweep.
"""

import sys
import types
from datetime import UTC, datetime, timedelta

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from typing import cast

import jwt
import pytest
from config import settings
from fastapi.testclient import TestClient
from models.refresh_token import RefreshToken
from services.auth_service import (
    ALGORITHM,
    AUDIENCE,
    ISSUER,
    TOKEN_TYPE_REFRESH,
    create_refresh_token,
    hash_password,
)
from services.refresh_token_service import (
    RefreshTokenInvalid,
    purge_expired_tokens,
    rotate_refresh_token,
)

_TEST_SECRET = "test-secret-key-for-refresh-rotation"  # noqa: S105 — test fixture, not a real secret


def _configure_auth() -> None:
    # conftest._restore_mutable_settings reverts these after each test.
    settings.secret_key = _TEST_SECRET
    settings.auth_password = hash_password("s3cret")


def _login(client: TestClient) -> dict:
    response = client.post("/auth/login", json={"password": "s3cret"})
    assert response.status_code == 200
    return cast(dict, response.json())


def _claims(token: str) -> dict:
    return cast(dict, jwt.decode(token, options={"verify_signature": False}))


def _jti(token: str) -> str:
    return cast(str, _claims(token)["jti"])


def _row(db_session, jti: str) -> RefreshToken | None:
    return cast("RefreshToken | None", db_session.query(RefreshToken).filter_by(jti=jti).first())


def test_login_registers_refresh_token(client: TestClient, db_session):
    _configure_auth()
    pair = _login(client)

    row = _row(db_session, _jti(pair["refresh_token"]))
    assert row is not None
    assert row.user_id == 1
    assert row.family_id
    assert row.consumed_at is None
    assert row.revoked_at is None
    # The family id is carried in the token for traceability.
    assert _claims(pair["refresh_token"])["fam"] == row.family_id


def test_refresh_rotation_happy_path(client: TestClient, db_session):
    _configure_auth()
    pair = _login(client)

    response = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert response.status_code == 200
    rotated = response.json()
    assert rotated["refresh_token"] != pair["refresh_token"]

    # The presented jti is consumed; its successor shares the family.
    old_row = _row(db_session, _jti(pair["refresh_token"]))
    new_row = _row(db_session, _jti(rotated["refresh_token"]))
    assert old_row is not None and old_row.consumed_at is not None
    assert new_row is not None and new_row.consumed_at is None
    assert new_row.family_id == old_row.family_id

    # The successor is itself redeemable.
    second = client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert second.status_code == 200


def test_refresh_reuse_revokes_family(client: TestClient, db_session):
    """Re-presenting a consumed token → 401, and the whole family dies."""
    _configure_auth()
    pair = _login(client)

    rotated = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).json()

    # Replay the consumed token — reuse detected.
    replay = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert replay.status_code == 401

    # Family revocation: even the legitimately-rotated successor is dead.
    successor = client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert successor.status_code == 401

    consumed_row = _row(db_session, _jti(pair["refresh_token"]))
    assert consumed_row is not None
    family_id = consumed_row.family_id
    rows = db_session.query(RefreshToken).filter_by(family_id=family_id).all()
    assert rows and all(r.revoked_at is not None for r in rows)


def test_refresh_rejects_unregistered_jti(client: TestClient):
    """A well-signed refresh JWT whose jti was never recorded → 401.

    Covers tokens minted before #1457 (no row) and any token issued outside
    the tracked issue path.
    """
    _configure_auth()
    loose = create_refresh_token(user_id=1, username="user")
    response = client.post("/auth/refresh", json={"refresh_token": loose})
    assert response.status_code == 401


def test_refresh_rejects_forged_unknown_jti(client: TestClient):
    """A crafted token with a made-up jti must not mint a new pair."""
    _configure_auth()
    forged = jwt.encode(
        {
            "sub": "1",
            "typ": TOKEN_TYPE_REFRESH,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(days=1),
            "jti": "attacker-controlled-jti",
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    assert client.post("/auth/refresh", json={"refresh_token": forged}).status_code == 401


def test_logout_revokes_family(client: TestClient):
    _configure_auth()
    pair = _login(client)
    rotated = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).json()

    response = client.post("/auth/logout", json={"refresh_token": rotated["refresh_token"]})
    assert response.status_code == 200

    # Both the presented token and the rest of the family are dead.
    assert client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401


def test_logout_is_idempotent_and_no_oracle(client: TestClient):
    """Logout always returns the same response — valid, invalid or empty."""
    _configure_auth()
    assert client.post("/auth/logout", json={"refresh_token": "not.a.jwt"}).status_code == 200
    assert client.post("/auth/logout", json={}).status_code == 200
    pair = _login(client)
    assert client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]}).status_code == 200
    assert client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]}).status_code == 200


def test_logout_does_not_touch_other_families(client: TestClient):
    _configure_auth()
    pair_a = _login(client)
    pair_b = _login(client)

    client.post("/auth/logout", json={"refresh_token": pair_b["refresh_token"]})

    # Family B is dead; family A still rotates fine.
    assert client.post("/auth/refresh", json={"refresh_token": pair_b["refresh_token"]}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": pair_a["refresh_token"]}).status_code == 200


def test_rotate_rejects_expired_row(db_session):
    """A tracked jti whose expires_at has passed → invalid (service level)."""
    from services.refresh_token_service import issue_refresh_token

    _configure_auth()
    token = issue_refresh_token(db_session, user_id=1, username="user")
    row = _row(db_session, _jti(token))
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(RefreshTokenInvalid):
        rotate_refresh_token(db_session, _jti(token))


def test_purge_expired_tokens(db_session):
    """The lazy sweep deletes expired rows but keeps live/consumed ones."""
    from services.refresh_token_service import issue_refresh_token

    _configure_auth()
    live = issue_refresh_token(db_session, user_id=1, username="user")
    stale = issue_refresh_token(db_session, user_id=1, username="user")
    stale_row = _row(db_session, _jti(stale))
    stale_row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    purged = purge_expired_tokens(db_session)
    assert purged == 1
    assert _row(db_session, _jti(stale)) is None
    assert _row(db_session, _jti(live)) is not None
