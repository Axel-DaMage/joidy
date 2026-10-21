"""Regression coverage for #991: the suite is hermetic against a populated .env.

conftest points ``JOIDY_ENV_FILE`` at an isolated file before app modules are
imported, so ``get_persisted()``/``read_env()``/``write_env()`` and the
pydantic ``Settings`` never see the developer's real ``.env``. These tests pin
down that mechanism; the CI step running the full suite with a populated
``.env`` proves the end-to-end behaviour.
"""

from pathlib import Path

from services.env_file import get_env_file, get_persisted, read_env, write_env


def test_env_file_is_not_the_repo_dotenv():
    """The resolved env file must be the isolated test file, not ./.env or /app/.env."""
    env_file = get_env_file()
    assert env_file.is_absolute()
    assert env_file.name in (".env", "joidy.env")
    assert env_file != Path("/app/.env")
    assert env_file != Path(__file__).parent.parent.parent / ".env"


def test_persisted_values_default_to_empty():
    """Without the opt-in fixture seeding values, nothing is persisted."""
    assert get_persisted("AUTH_PASSWORD") == ""
    assert get_persisted("SECRET_KEY") == ""
    assert get_persisted("OBSIDIAN_WEBHOOK_SECRET") == ""


def test_persisted_env_fixture_seeds_values(persisted_env):
    persisted_env.write_text("AUTH_PASSWORD=seeded-password\nSECRET_KEY=seeded-secret\n")
    assert get_persisted("AUTH_PASSWORD") == "seeded-password"
    assert read_env()["SECRET_KEY"] == "seeded-secret"


def test_write_env_lands_in_isolated_file(persisted_env):
    write_env({"FOO": "bar"})
    assert read_env() == {"FOO": "bar"}
    assert persisted_env.read_text().strip() == "FOO=bar"
