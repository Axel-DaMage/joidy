"""Base-URL validation tests (#1330).

Provider base URLs are a cleartext-exfiltration surface: http:// is only
acceptable for loopback targets (Ollama is expected to be local), remote
hosts must use https://, and anything else must be refused — both at
Settings() construction (fail-fast startup) and at client init.
"""

import unittest
from unittest.mock import patch

import pytest
from config import Settings, _is_loopback_host, validate_base_url
from pydantic import ValidationError


@pytest.fixture
def _clean_url_env(monkeypatch):
    """Drop env vars that could leak a developer's real config into Settings()."""
    for var in ("OPENAI_BASE_URL", "OLLAMA_BASE_URL", "ALLOW_INSECURE_BASE_URLS"):
        monkeypatch.delenv(var, raising=False)


class TestIsLoopbackHost:
    @pytest.mark.parametrize(
        "host",
        [
            "localhost",
            "foo.localhost",
            "127.0.0.1",
            "127.55.0.99",  # whole 127.0.0.0/8 is loopback
            "::1",
            "host.docker.internal",
            "host.containers.internal",
        ],
    )
    def test_loopback_hosts(self, host):
        assert _is_loopback_host(host) is True

    @pytest.mark.parametrize(
        "host",
        ["evil.example.com", "8.8.8.8", "192.168.1.10", "10.0.0.2", "ollama", "0.0.0.0"],
    )
    def test_non_loopback_hosts(self, host):
        assert _is_loopback_host(host) is False


class TestValidateBaseUrl:
    def test_https_remote_allowed(self):
        assert validate_base_url("https://api.example.com/v1") == "https://api.example.com/v1"

    def test_trailing_slash_normalized(self):
        assert validate_base_url("http://localhost:11434/") == "http://localhost:11434"

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://[::1]:11434",
            "http://host.docker.internal:11434",
            "http://host.containers.internal:11434",
            "http://foo.localhost:11434",
            "https://localhost:11434",
        ],
    )
    def test_http_loopback_variants_allowed(self, url):
        assert validate_base_url(url) == url.rstrip("/")

    @pytest.mark.parametrize(
        "url",
        [
            "http://evil.example.com",
            "http://8.8.8.8",
            "http://192.168.1.50:11434",  # LAN host — still cleartext
            "http://ollama:11434",  # sibling-container name — needs opt-in
        ],
    )
    def test_http_non_loopback_refused(self, url):
        with pytest.raises(ValueError, match="loopback"):
            validate_base_url(url, name="OLLAMA_BASE_URL")

    def test_missing_scheme_refused(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_base_url("evil.example.com:11434")

    def test_non_http_scheme_refused(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_base_url("ftp://localhost:21")

    def test_allow_insecure_downgrades_to_warning(self, caplog):
        with caplog.at_level("WARNING"):
            result = validate_base_url("http://ollama:11434", allow_insecure=True)
        assert result == "http://ollama:11434"
        assert "ALLOW_INSECURE_BASE_URLS" in caplog.text

    def test_error_message_points_to_override(self):
        with pytest.raises(ValueError, match="ALLOW_INSECURE_BASE_URLS"):
            validate_base_url("http://evil.example.com")


class TestSettingsStartupValidation:
    """A tampered env must be refused at Settings() construction (#1330)."""

    def test_openai_base_url_remote_http_refused(self, _clean_url_env):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, openai_base_url="http://evil.example.com/v1")

    def test_ollama_base_url_remote_http_refused(self, _clean_url_env):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, ollama_base_url="http://192.168.1.50:11434")

    def test_ollama_loopback_accepted(self, _clean_url_env):
        s = Settings(_env_file=None, ollama_base_url="http://localhost:11434")
        assert s.ollama_base_url == "http://localhost:11434"

    def test_ollama_host_docker_internal_accepted(self, _clean_url_env):
        # The documented default in .env.example must keep working.
        s = Settings(_env_file=None, ollama_base_url="http://host.docker.internal:11434")
        assert s.ollama_base_url == "http://host.docker.internal:11434"

    def test_allow_insecure_opt_in_accepted(self, _clean_url_env):
        s = Settings(
            _env_file=None,
            ollama_base_url="http://ollama:11434",
            allow_insecure_base_urls=True,
        )
        assert s.ollama_base_url == "http://ollama:11434"


class TestClientInitValidation(unittest.TestCase):
    """Defense in depth: clients also reject bad base URLs at construction."""

    def test_ollama_client_refuses_remote_http(self):
        from clients.ollama import OllamaClient

        with self.assertRaises(ValueError):
            OllamaClient(base_url="http://remote.example.com:11434", model="llama3")

    def test_openai_client_refuses_remote_http(self):
        from clients.openai import OpenAIClient

        with self.assertRaises(ValueError):
            OpenAIClient(api_key="k", model="m", base_url="http://evil.example.com/v1")

    def test_openai_client_accepts_https_remote(self):
        from clients.openai import OpenAIClient

        with patch("clients.openai.AsyncOpenAI"):
            client = OpenAIClient(api_key="k", model="m", base_url="https://router.example.com/v1")
        self.assertEqual(client.provider_name, "openai")


if __name__ == "__main__":
    unittest.main()
