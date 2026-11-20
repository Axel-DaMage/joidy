"""Refresh-token persistence: rotation tracking + reuse detection (#1457).

``POST /auth/login`` calls :func:`issue_refresh_token` with no family to
start a session; ``POST /auth/refresh`` calls :func:`rotate_refresh_token`,
which atomically consumes the presented ``jti`` and mints its successor in
the same family. Presenting an already-consumed ``jti`` is a replay — a
racing client or a stolen credential — so the whole family is revoked and
the request fails closed with 401.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast

from config import settings
from models.refresh_token import RefreshToken
from services.auth_service import create_refresh_token
from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RefreshTokenError(Exception):
    """Base class for refresh-token rotation failures (all map to HTTP 401)."""


class RefreshTokenInvalid(RefreshTokenError):
    """The presented jti is unknown, revoked or expired."""


class RefreshTokenReuse(RefreshTokenError):
    """A consumed jti was presented again — theft signal; family revoked."""


def _now() -> datetime:
    """Naive UTC now, matching the ``DateTime`` columns used by the schema."""
    return datetime.now(UTC).replace(tzinfo=None)


def issue_refresh_token(
    db: Session,
    user_id: int,
    username: str,
    family_id: str | None = None,
) -> str:
    """Mint a refresh token and register its ``jti`` in ``refresh_tokens``.

    ``family_id=None`` starts a new family (login); passing the consumed
    token's family continues the rotation chain. The same ``jti``/``family``
    go into the JWT claims (``jti``/``fam``) and the row, so the database —
    not the token — is the source of truth at redemption time.
    """
    jti = secrets.token_urlsafe(16)
    family = family_id or secrets.token_urlsafe(16)
    now = _now()
    token = create_refresh_token(user_id, username, jti=jti, family_id=family)
    db.add(
        RefreshToken(
            jti=jti,
            family_id=family,
            user_id=user_id,
            username=username or "",
            issued_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    db.commit()
    return token


def rotate_refresh_token(db: Session, jti: str) -> str:
    """Consume ``jti`` and mint its successor in the same family.

    The consume is a conditional ``UPDATE ... WHERE consumed_at IS NULL`` so
    two concurrent presentations of the same token cannot both redeem: the
    loser's statement matches zero rows and falls into the reuse path below,
    revoking the family — fail closed by design.

    Raises :class:`RefreshTokenInvalid` for unknown/revoked/expired jtis and
    :class:`RefreshTokenReuse` after revoking the family on replay.
    """
    now = _now()
    consumed = cast(
        CursorResult,
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.jti == jti,
                RefreshToken.consumed_at.is_(None),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .values(consumed_at=now)
        ),
    )
    if consumed.rowcount == 1:
        consumed_row = db.query(RefreshToken).filter_by(jti=jti).one()
        return issue_refresh_token(db, consumed_row.user_id, consumed_row.username, consumed_row.family_id)

    row = db.query(RefreshToken).filter_by(jti=jti).first()
    if row is None or row.revoked_at is not None:
        # Unknown jti (pre-#1457 token, forged, or family already killed) or
        # an explicitly revoked one — plain rejection, nothing left to do.
        raise RefreshTokenInvalid("unknown or revoked refresh token")
    if row.consumed_at is not None:
        # The jti exists and was already redeemed: replay. Assume theft and
        # revoke the whole family — both the attacker's copy and every token
        # derived from this chain die together.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        logger.warning(
            "refresh-token reuse detected (user=%s family=%s) — family revoked",
            row.user_id,
            row.family_id,
        )
        raise RefreshTokenReuse("consumed refresh token presented again")
    # Row exists, unconsumed, but the atomic UPDATE matched 0 rows — only
    # expiry remains (expires_at <= now).
    raise RefreshTokenInvalid("expired refresh token")


def revoke_family_by_jti(db: Session, jti: str) -> bool:
    """Revoke the whole family containing ``jti`` (logout). True if it existed."""
    row = db.query(RefreshToken).filter_by(jti=jti).first()
    if row is None:
        return False
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    db.commit()
    return True


def purge_expired_tokens(db: Session) -> int:
    """Delete rows past ``expires_at``; called lazily from login/refresh.

    Consumed-but-unexpired rows are kept on purpose: their ``consumed_at``
    marker is what makes replay detection work for the token's full JWT
    lifetime.
    """
    result = cast(
        CursorResult,
        db.execute(delete(RefreshToken).where(RefreshToken.expires_at < _now())),
    )
    db.commit()
    return result.rowcount or 0
