"""High level power comes from mastering a jutsu, not just farming levels."""
import unittest

import combat
import leveling
from models import Player


class HighLevelJutsuMasteryTests(unittest.TestCase):
    def test_breakthroughs_require_real_mastery(self):
        jutsu = {"display_name": "Rasengan"}
        player = Player("Breakthrough", "Breakthrough", level=250)
        player.skill_proficiencies["Rasengan"] = 99
        self.assertEqual(combat.mastered_jutsu_breakthrough_percent(player, jutsu), 0)
        player.skill_proficiencies["Rasengan"] = 100
        self.assertEqual(combat.mastered_jutsu_breakthrough_percent(player, jutsu), 14)
        player.skill_proficiencies["Rasengan"] = 150
        self.assertEqual(combat.mastered_jutsu_breakthrough_percent(player, jutsu), 14)

    def test_breakthrough_milestones_and_preserved_early_pacing(self):
        jutsu = {"display_name": "Rasengan"}
        player = Player("Breakthrough", "Breakthrough")
        player.skill_proficiencies["Rasengan"] = 100
        expected = {99: 0, 100: 2, 124: 2, 125: 4, 149: 4,
                    150: 6, 175: 8, 200: 10, 225: 12, 250: 14}
        for level, percent in expected.items():
            player.level = level
            self.assertEqual(
                combat.mastered_jutsu_breakthrough_percent(player, jutsu),
                percent,
            )

    def test_rank_caps_and_final_level(self):
        self.assertEqual(leveling.MAX_LEVEL, 250)
        self.assertEqual(leveling.rank_level_cap(Player(
            "Elite", "Elite", village_rank="elite jonin", level=249)), 250)


if __name__ == "__main__":
    unittest.main()
