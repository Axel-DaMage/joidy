import unittest

from config import settings
from services import gamification_engine


class GamificationConfigTests(unittest.TestCase):
    def setUp(self):
        gamification_engine._xp_table_cache = None
        gamification_engine._plant_stages_cache = None

    def tearDown(self) -> None:
        settings.xp_table_json = ""
        gamification_engine._xp_table_cache = None
        gamification_engine._plant_stages_cache = None

    def test_xp_table_json_overrides_default_event_value(self) -> None:
        settings.xp_table_json = '{"note_created": 42}'

        self.assertEqual(gamification_engine.xp_for("note_created", None), 42)
        self.assertEqual(gamification_engine.xp_for("daily_activity", None), 15)

    def test_invalid_xp_table_json_falls_back_to_defaults(self) -> None:
        settings.xp_table_json = "{bad-json}"

        self.assertEqual(gamification_engine.xp_for("note_created", None), 10)


if __name__ == "__main__":
    unittest.main()
