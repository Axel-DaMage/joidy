"""Shared field-level encryption for secrets and sensitive data at rest (#1286, #1329).

Single Fernet scheme for every encrypted column: the key is derived from the
app's ``SECRET_KEY`` exactly like the existing ``GoogleToken.refresh_token``
encryption (SHA-256 → urlsafe-base64 → Fernet key), so one secret protects
all encrypted columns — and rotating it invalidates them all at once.

Fields that must stay searchable in SQL (equality/ILIKE) cannot use this:
Fernet is non-deterministic, so ciphertext never matches a literal filter.
"""

import base64
import hashlib
import logging

from config import settings
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)


def get_fernet() -> Fernet:
    """Derive a Fernet instance from the app's SECRET_KEY.

    Rebuilt on every call (no caching) so a changed ``settings.secret_key``
    takes effect immediately — matching the original
    ``google_token_service._get_fernet()`` semantics.
    """
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_str(value: str) -> str:
    """Encrypt a string, returning the Fernet token (ciphertext)."""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_str(encrypted: str) -> str | None:
    """Decrypt a Fernet token. Returns None on invalid ciphertext (fail closed)."""
    try:
        return get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt value (invalid Fernet token)")
        return None


def decrypt_str_or_plaintext(value: str) -> str:
    """Decrypt a Fernet token, or return ``value`` unchanged when it is not
    valid ciphertext — i.e. a row written before encryption-at-rest landed.

    Legacy plaintext stays readable and is transparently re-encrypted on the
    next write (lazy migration). The migration also encrypts existing rows
    eagerly, so this path is only a safety net.
    """
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return value


class EncryptedText(TypeDecorator):
    """``Text`` column transparently encrypted at rest with Fernet.

    - ``process_bind_param`` encrypts on write; ``process_result_value``
      decrypts on read, falling back to the raw value for rows written
      before encryption was enabled (lazy migration).
    - Ciphertext never matches equality/ILIKE filters — keep searchable
      columns on plain ``Text``/``String``.
    - Impl is ``Text`` so ciphertext (larger than plaintext) always fits;
      converting a bounded ``String(n)`` column needs an ``ALTER COLUMN``.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001, ANN202
        if value is None:
            return None
        return encrypt_str(str(value))

    def process_result_value(self, value, dialect):  # noqa: ANN001, ANN202
        if value is None:
            return None
        return decrypt_str_or_plaintext(value)
