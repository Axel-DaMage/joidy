import unittest
from time import monotonic
from typing import cast
from unittest.mock import patch

from config import settings
from services import gamification_engine
from sqlalchemy.orm import Session


class GamificationConfigTests(unittest.TestCase):
    def setUp(self):
        gamification_engine._xp_table_cache = None
        gamification_engine._plant_stages_cache = None
        gamification_engine._db_config_cache = None

    def tearDown(self) -> None:
        settings.xp_table_json = ""
        gamification_engine._xp_table_cache = None
        gamification_engine._plant_stages_cache = None
        gamification_engine._db_config_cache = None

    def test_xp_table_json_overrides_default_event_value(self) -> None:
        settings.xp_table_json = '{"note_created": 42}'

        self.assertEqual(gamification_engine.xp_for("note_created", None), 42)
        self.assertEqual(gamification_engine.xp_for("daily_activity", None), 15)

    def test_invalid_xp_table_json_falls_back_to_defaults(self) -> None:
        settings.xp_table_json = "{bad-json}"

        self.assertEqual(gamification_engine.xp_for("note_created", None), 10)

    def test_load_config_from_db_caches_within_ttl(self) -> None:
        """#1515: repeated reads inside the TTL must not re-scan system_config."""
        db = cast(Session, None)
        with patch.object(
            gamification_engine.ConfigRepository,
            "get_all_as_dict",
            return_value={"xp_note_created": "42"},
        ) as mocked:
            first = gamification_engine.load_config_from_db(db)
            second = gamification_engine.load_config_from_db(db)
        self.assertEqual(first, {"xp_note_created": "42"})
        self.assertIs(first, second)
        self.assertEqual(mocked.call_count, 1)

    def test_load_config_from_db_refetches_after_ttl(self) -> None:
        db = cast(Session, None)
        gamification_engine._db_config_cache = (monotonic() - 999.0, {"stale": "1"})
        with patch.object(
            gamification_engine.ConfigRepository,
            "get_all_as_dict",
            return_value={"xp_note_created": "42"},
        ) as mocked:
            config = gamification_engine.load_config_from_db(db)
        self.assertEqual(config, {"xp_note_created": "42"})
        self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
