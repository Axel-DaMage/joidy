"""Coverage for the stat-keyed .env parse cache (#1518).

read_env() used to open and re-parse the whole file on every call — ~7-10
times per authenticated request. It now caches the parsed dict keyed on
``(path, mtime_ns, ctime_ns, size)`` so repeated reads pay a single stat()
while writes from any process still become visible on the next call (the
cross-worker freshness get_persisted() requires).
"""

from unittest.mock import patch

import services.env_file as env_file_module
from services.env_file import get_persisted, read_env, write_env


def test_read_env_reparses_only_after_change(persisted_env):
    """Repeated reads of an unchanged file must not re-open/re-parse it."""
    persisted_env.write_text("FOO=one\n")
    real_parse = env_file_module._parse_env_file
    with patch.object(env_file_module, "_parse_env_file", wraps=real_parse) as parse:
        assert read_env()["FOO"] == "one"
        assert read_env()["FOO"] == "one"
        read_env()
        assert parse.call_count == 1

        # A write bumps the (mtime, ctime, size) signature → next read re-parses.
        persisted_env.write_text("FOO=two\nBAR=baz\n")
        assert read_env()["FOO"] == "two"
        assert read_env()["BAR"] == "baz"
        assert parse.call_count == 2
        assert parse.call_args.args[0] == persisted_env


def test_write_env_updates_cached_view(persisted_env):
    """Writes through write_env() are visible without manual cache clearing."""
    assert read_env() == {}
    write_env({"SECRET_KEY": "abc123"})
    assert get_persisted("SECRET_KEY") == "abc123"
    assert read_env() == {"SECRET_KEY": "abc123"}


def test_read_env_cache_is_keyed_by_path(persisted_env, tmp_path, monkeypatch):
    """Repointing JOIDY_ENV_FILE must never serve a stale entry."""
    persisted_env.write_text("FOO=one\n")
    assert read_env()["FOO"] == "one"

    other = tmp_path / "other.env"
    other.write_text("FOO=two\n")
    monkeypatch.setenv("JOIDY_ENV_FILE", str(other))
    assert read_env()["FOO"] == "two"

    monkeypatch.setenv("JOIDY_ENV_FILE", str(persisted_env))
    assert read_env()["FOO"] == "one"


def test_read_env_missing_file_returns_empty(persisted_env):
    """Missing file stays graceful: {} (and a stale entry is not revived)."""
    persisted_env.write_text("FOO=one\n")
    assert read_env()["FOO"] == "one"
    persisted_env.unlink()
    assert read_env() == {}
    assert get_persisted("FOO") == ""


def test_read_env_directory_returns_empty(persisted_env):
    """The Docker bind-mount-directory edge case still yields {} (#991)."""
    persisted_env.unlink()
    persisted_env.mkdir()
    assert read_env() == {}


def test_read_env_returns_fresh_dict(persisted_env):
    """Callers mutating the returned dict must not corrupt the cache."""
    persisted_env.write_text("FOO=bar\n")
    env = read_env()
    env["FOO"] = "mutated"
    env["EXTRA"] = "x"
    assert read_env() == {"FOO": "bar"}
