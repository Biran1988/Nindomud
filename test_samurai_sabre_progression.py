"""Regression tests for Samurai Sabre's passive damage progression."""
import unittest
from unittest.mock import patch

import ninja_arts
import samurai_sabre_progression as sabre
from models import Player


class TestSamuraiSabrePassives(unittest.TestCase):
    def make_player(self, level, *, combat_class="bukijutsu"):
        player = Player("SabreTester", "SabreTester", level=level,
                        primary_class=combat_class)
        player.equipment["wielded"] = "A Basic Sword"
        player.learned_skills.append("Samurai Sabre")
        return player

    def test_tiers_unlock_automatically_and_are_already_mastered(self):
        player = self.make_player(35)
        self.assertEqual(sabre.sync_passives(player), [])
        for name, level in sabre.PASSIVE_UNLOCKS.items():
            player.level = level
            self.assertEqual(sabre.sync_passives(player), [name])
            self.assertEqual(player.skill_proficiencies[name], 100)
            self.assertEqual(sabre.sync_passives(player), [])

    def test_base_and_all_four_bonus_thresholds(self):
        for level, expected in ((35, 5), (84, 5), (85, 10),
                                (139, 10), (140, 15), (194, 15),
                                (195, 20), (249, 20), (250, 25)):
            with self.subTest(level=level):
                p = self.make_player(level)
                sabre.sync_passives(p)
                p.samurai_sabre_active = True
                self.assertEqual(sabre.damage_bonus_percent(p), expected)
                self.assertEqual(ninja_arts.weapon_hit(p, p, 100),
                                 100 + expected)

    def test_passives_require_active_base_and_wielded_sword(self):
        p = self.make_player(250)
        sabre.sync_passives(p)
        self.assertEqual(sabre.damage_bonus_percent(p), 0)
        p.samurai_sabre_active = True
        self.assertEqual(sabre.damage_bonus_percent(p), 25)
        p.equipment["wielded"] = "A Basic Kunai"
        self.assertEqual(sabre.damage_bonus_percent(p), 0)
        p.equipment["wielded"] = "A Basic Sword"
        p.primary_class = "ninjutsu"
        self.assertEqual(sabre.damage_bonus_percent(p), 0)

    def test_no_upgrade_unlocks_for_non_bukijutsu(self):
        p = self.make_player(250, combat_class="ninjutsu")
        self.assertEqual(sabre.sync_passives(p), [])
        self.assertFalse(any(x.startswith("Samurai Sabre ") for x in
                             p.learned_skills))


if __name__ == "__main__":
    unittest.main()
