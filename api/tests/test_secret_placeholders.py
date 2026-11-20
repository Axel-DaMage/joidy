"""Regression tests for #1393 — shipped placeholder secrets must never be honored.

``.env.example`` publishes ``SECRET_KEY=change_this_to_a_random_secret_key``.
A deployment created by ``cp .env.example .env`` bypasses every write-path
filter (the settings UI refuses the placeholder, a manual copy does not), so
the auth layer must treat those values as unset at *use* time — otherwise
JWTs, OAuth state HMACs and Fernet-encrypted tokens are produced under a key
anyone can read from this repository.
"""

import sys
import types

import pytest

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from services import google_token_service, oauth_state
from services.auth_service import (
    _effective_secret_key,
    create_access_token,
    verify_internal_token,
    verify_token,
)
from services.env_file import is_placeholder_env_value

PLACEHOLDERS = [
    "change_this_to_a_random_secret_key",  # shipped verbatim in .env.example
    "dev_secret_change_me",  # legacy config.py default
    "your_gemini_api_key_here",
    "changeme",
    "secret",
]

REAL_SECRET = "9f8e7d6c5b4a3210f1e2d3c4b5a69788706f5e4d3c2b1a09"  # noqa: S105 — test-only value


class TestPlaceholderDetection:
    @pytest.mark.parametrize("value", PLACEHOLDERS)
    def test_placeholders_detected_case_and_whitespace_insensitive(self, value):
        assert is_placeholder_env_value(value)
        assert is_placeholder_env_value(f"  {value.upper()}  ")

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_empty_and_blank_count_as_unset(self, value):
        assert is_placeholder_env_value(value)

    def test_real_secret_not_flagged(self):
        assert not is_placeholder_env_value(REAL_SECRET)


class TestSecretKeyPlaceholders:
    @pytest.mark.parametrize("value", PLACEHOLDERS)
    def test_settings_placeholder_treated_as_unset(self, monkeypatch, value):
        """A placeholder SECRET_KEY must refuse token creation (#1393)."""
        monkeypatch.setattr(settings, "secret_key", value)
        assert _effective_secret_key() == ""
        with pytest.raises(ValueError):
            create_access_token(1)
        assert verify_token("header.payload.signature") is None

    def test_persisted_placeholder_treated_as_unset(self, persisted_env, monkeypatch):
        """The placeholder in the deployment .env itself is rejected too."""
        persisted_env.write_text("SECRET_KEY=change_this_to_a_random_secret_key\n")
        monkeypatch.setattr(settings, "secret_key", "")
        assert _effective_secret_key() == ""
        with pytest.raises(ValueError):
            create_access_token(1)

    def test_persisted_placeholder_does_not_shadow_real_fallback(self, persisted_env, monkeypatch):
        """A placeholder in .env must not hide a real key from the process env."""
        persisted_env.write_text("SECRET_KEY=change_this_to_a_random_secret_key\n")
        monkeypatch.setattr(settings, "secret_key", REAL_SECRET)
        assert _effective_secret_key() == REAL_SECRET
        assert create_access_token(1)

    def test_persisted_real_key_takes_precedence(self, persisted_env, monkeypatch):
        persisted_env.write_text(f"SECRET_KEY={REAL_SECRET}\n")
        monkeypatch.setattr(settings, "secret_key", "other-key")
        assert _effective_secret_key() == REAL_SECRET


class TestInternalTokenPlaceholders:
    @pytest.mark.parametrize("value", PLACEHOLDERS)
    def test_placeholder_token_rejected(self, monkeypatch, value):
        """INTERNAL_API_TOKEN set to a known value must not authenticate."""
        monkeypatch.setattr(settings, "internal_api_token", value)
        assert not verify_internal_token(value)

    def test_real_token_still_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "real-service-token")
        assert verify_internal_token("real-service-token")


class TestOAuthStatePlaceholders:
    @pytest.mark.parametrize("value", PLACEHOLDERS)
    def test_generate_state_refused_with_placeholder(self, monkeypatch, value):
        """OAuth state HMACs must not be keyed with a published secret."""
        monkeypatch.setattr(settings, "secret_key", value)
        with pytest.raises(RuntimeError):
            oauth_state.generate_state("github")
        assert not oauth_state.verify_state("github.nonce.0.sig", "github")

    def test_real_key_still_signs_states(self, monkeypatch):
        monkeypatch.setattr(settings, "secret_key", REAL_SECRET)
        state = oauth_state.generate_state("github")
        assert oauth_state.verify_state(state, "github")


class TestFernetKeyPlaceholders:
    """google_token_service derives its Fernet key from SECRET_KEY — a
    placeholder would encrypt stored refresh tokens under a published key."""

    @pytest.mark.parametrize("value", PLACEHOLDERS)
    def test_encrypt_refused_with_placeholder(self, monkeypatch, value):
        monkeypatch.setattr(settings, "secret_key", value)
        with pytest.raises(RuntimeError):
            google_token_service.encrypt_token("refresh-token")
        # Decryption fails closed too: existing ciphertext reads as absent.
        assert google_token_service.decrypt_token("anything") is None

    def test_real_key_still_encrypts(self, monkeypatch):
        monkeypatch.setattr(settings, "secret_key", REAL_SECRET)
        assert google_token_service.decrypt_token(google_token_service.encrypt_token("tok")) == "tok"
