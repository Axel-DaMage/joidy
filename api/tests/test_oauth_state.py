"""Unit tests for services.oauth_state — HMAC-signed OAuth state (#1280)."""

import time

import pytest
from services import oauth_state


def _key() -> str:
    return "test-secret"


def test_generate_and_verify_round_trip(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", _key())
    state = oauth_state.generate_state("google")
    assert oauth_state.verify_state(state, "google") is True


def test_generated_states_are_unique(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", _key())
    assert oauth_state.generate_state("google") != oauth_state.generate_state("google")


def test_verify_rejects_tampered_state(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", _key())
    state = oauth_state.generate_state("google")

    parts = state.split(".")
    parts[1] = "forgednonce000000000"  # different nonce, same signature
    assert oauth_state.verify_state(".".join(parts), "google") is False

    parts = state.split(".")
    parts[3] = "0" * 64  # forged signature
    assert oauth_state.verify_state(".".join(parts), "google") is False


def test_verify_rejects_wrong_provider(monkeypatch):
    # A state minted for one provider must not pass at another's callback.
    monkeypatch.setattr("config.settings.secret_key", _key())
    assert oauth_state.verify_state(oauth_state.generate_state("google"), "github") is False
    assert oauth_state.verify_state(oauth_state.generate_state("github"), "google") is False


def test_verify_rejects_malformed(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", _key())
    assert oauth_state.verify_state("garbage", "google") is False
    assert oauth_state.verify_state("", "google") is False
    assert oauth_state.verify_state("google.nonce.123", "google") is False
    assert oauth_state.verify_state("google.nonce.notanint.sig", "google") is False


def test_verify_rejects_stale_and_future_timestamps(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", _key())
    now = int(time.time())
    for issued_at in (now - oauth_state.STATE_TTL_SECONDS - 5, now + 300):
        payload = f"google.abc123.{issued_at}"
        state = f"{payload}.{oauth_state._signature(_key(), payload)}"
        assert oauth_state.verify_state(state, "google") is False


def test_verify_respects_custom_max_age(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", _key())
    issued_at = int(time.time()) - 30
    payload = f"google.abc123.{issued_at}"
    state = f"{payload}.{oauth_state._signature(_key(), payload)}"
    assert oauth_state.verify_state(state, "google", max_age=60) is True
    assert oauth_state.verify_state(state, "google", max_age=10) is False


def test_secret_key_required(monkeypatch):
    monkeypatch.setattr("config.settings.secret_key", "")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        oauth_state.generate_state("google")
