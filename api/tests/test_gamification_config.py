import unittest

from config import settings
from services import gamification_engine


class GamificationConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        settings.xp_table_json = ""
        gamification_engine.get_xp_table.cache_clear()

    def test_xp_table_json_overrides_default_event_value(self) -> None:
        settings.xp_table_json = '{"note_created": 42}'
        gamification_engine.get_xp_table.cache_clear()

        self.assertEqual(gamification_engine.xp_for("note_created"), 42)
        self.assertEqual(gamification_engine.xp_for("daily_activity"), 15)

    def test_invalid_xp_table_json_falls_back_to_defaults(self) -> None:
        settings.xp_table_json = "{bad-json}"
        gamification_engine.get_xp_table.cache_clear()

        self.assertEqual(gamification_engine.xp_for("note_created"), 10)


if __name__ == "__main__":
    unittest.main()
