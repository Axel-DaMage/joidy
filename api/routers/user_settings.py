"""User-scoped JSON settings stored in the database (#969).

Provides a generic key/value store backed by the existing ``system_config``
table so per-user UI state (e.g. clock alarms) survives reloads and devices.
Values are namespaced under the ``user_settings:`` storage prefix so they can
never collide with gamification/system keys managed by ``ConfigRepository``
consumers elsewhere.
"""

import json
import re
from typing import Any

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from repositories import ConfigRepository
from sqlalchemy.orm import Session

router = APIRouter(prefix="/user-settings", tags=["user-settings"])

# Keys are client-chosen but constrained: lowercase slugs only, so a buggy or
# malicious client can't probe arbitrary system_config rows.
_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
_STORAGE_PREFIX = "user_settings:"
# 64 KiB is generous for UI blobs (an alarm is ~150 bytes) and keeps a
# runaway client from bloating system_config.
_MAX_VALUE_BYTES = 64 * 1024


class UserSettingPayload(BaseModel):
    """Arbitrary JSON blob persisted verbatim for a setting key."""

    value: Any


def _storage_key(key: str) -> str:
    if not _KEY_RE.match(key):
        raise HTTPException(status_code=422, detail="Invalid setting key")
    return f"{_STORAGE_PREFIX}{key}"


@router.get("/{key}")
def get_user_setting(key: str, db: Session = Depends(get_db)):
    """Return the stored JSON value for ``key``, or ``null`` if unset."""
    raw = ConfigRepository(db).get(_storage_key(key))
    value = None
    if raw is not None:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = None
    return {"key": key, "value": value}


@router.put("/{key}")
def put_user_setting(
    key: str,
    payload: UserSettingPayload,
    db: Session = Depends(get_db),
):
    """Store ``value`` (any JSON) under ``key``. Overwrites existing value."""
    skey = _storage_key(key)
    raw = json.dumps(payload.value)
    if len(raw.encode("utf-8")) > _MAX_VALUE_BYTES:
        raise HTTPException(status_code=413, detail="Setting value too large")
    ConfigRepository(db).set(skey, raw)
    db.commit()
    return {"key": key, "value": payload.value}
