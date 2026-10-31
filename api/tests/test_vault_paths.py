"""Unit tests for services/vault_paths — source_path domain normalization (#1099)."""

import sys
import types
import unittest
from unittest.mock import patch

# Stub sqlite_vec before importing any app modules
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from services.vault_paths import normalize_source_path


class TestNormalizeSourcePath(unittest.TestCase):
    def setUp(self) -> None:
        # Deterministic: container sees /vault, .env holds the host path.
        env = {"OBSIDIAN_VAULT_PATH": "/home/user/ObsidianVault"}
        self.env_patch = patch("services.vault_paths.read_env", return_value=env)
        self.env_patch.start()
        self.settings_patch = patch("services.vault_paths.settings.obsidian_vault_path", "/vault")
        self.settings_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.settings_patch.stop()

    def test_remaps_host_domain_onto_container_domain(self) -> None:
        self.assertEqual(
            normalize_source_path("/home/user/ObsidianVault/Daily/2025-01-01.md"),
            "/vault/Daily/2025-01-01.md",
        )

    def test_already_effective_domain_passes_through(self) -> None:
        self.assertEqual(
            normalize_source_path("/vault/Daily/2025-01-01.md"),
            "/vault/Daily/2025-01-01.md",
        )

    def test_remaps_windows_style_host_path(self) -> None:
        # The .env on Windows-style installs holds a backslash vault path; the
        # root must match after separator cleanup.
        env = {"OBSIDIAN_VAULT_PATH": "C:\\Users\\user\\ObsidianVault"}
        with patch("services.vault_paths.read_env", return_value=env):
            self.assertEqual(
                normalize_source_path("C:\\Users\\user\\ObsidianVault\\Daily\\note.md"),
                "/vault/Daily/note.md",
            )

    def test_traversal_is_not_remapped(self) -> None:
        # A traversal under a known root must not be re-anchored inside the
        # vault; the unknown root passes through and write_to_vault's prefix
        # guard refuses to write outside the vault.
        self.assertEqual(
            normalize_source_path("/home/user/ObsidianVault/../../etc/passwd"),
            "/home/user/ObsidianVault/../../etc/passwd",
        )

    def test_unknown_root_passes_through_unchanged(self) -> None:
        self.assertEqual(
            normalize_source_path("/somewhere/else/note.md"),
            "/somewhere/else/note.md",
        )

    def test_empty_path_returns_none(self) -> None:
        self.assertIsNone(normalize_source_path(None))
        self.assertIsNone(normalize_source_path("   "))

    def test_vault_root_existing_domain_returns_root(self) -> None:
        self.assertEqual(normalize_source_path("/vault"), "/vault")
        self.assertEqual(normalize_source_path("/vault/"), "/vault")


if __name__ == "__main__":
    unittest.main()
