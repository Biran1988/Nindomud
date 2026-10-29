"""Targeted Sharingan inheritance, strong-eye, and early-awakening regressions."""
import unittest
from unittest.mock import patch

import data_kekkei_genkai as kkg
from models import Player


class SharinganOddsTests(unittest.TestCase):
    def test_uchiha_chance_is_half_and_other_clans_unchanged(self):
        self.assertEqual(kkg.CLAN_INHERITANCE["uchiha"]["sharingan"], 0.50)
        self.assertEqual(kkg.CLAN_INHERITANCE["hyuga"]["byakugan"], 1.0)
        self.assertEqual(kkg.CLAN_INHERITANCE["kaguya"]["shikotsumyaku"], 0.25)
        with patch.object(kkg.random, "random", return_value=0.49), \
             patch.object(kkg.random, "randint", side_effect=[24, 94, 7, 97]) as rolls:
            inherited = kkg.roll_inheritance("uchiha")
        self.assertEqual(inherited, {"bloodline_id": "sharingan",
                                     "potential": 94, "talent": 97})
        self.assertEqual(rolls.call_count, 4)
        with patch.object(kkg.random, "random", return_value=0.50):
            self.assertEqual(kkg.roll_inheritance("uchiha"),
                             {"bloodline_id": None, "potential": 0, "talent": 0})

    def test_other_bloodlines_do_not_get_best_of_two(self):
        with patch.object(kkg.random, "random", return_value=0.20), \
             patch.object(kkg.random, "randint", side_effect=[15, 88]) as rolls:
            inherited = kkg.roll_inheritance("hyuga")
        self.assertEqual(inherited, {"bloodline_id": "byakugan",
                                     "potential": 15, "talent": 88})
        self.assertEqual(rolls.call_count, 2)

    def test_sharingan_first_tomoe_from_level_25(self):
        p = Player("Eye", "Eye", level=24)
        p.bloodline_id = "sharingan"
        with patch.object(kkg.random, "random", return_value=0):
            before = kkg.attempt_automatic_awakening(p)
        self.assertFalse(before["rolled"])
        self.assertEqual(p.bloodline_tomoe, 0)
        p.level = 25
        with patch.object(kkg.random, "random", return_value=0.005):
            awakened = kkg.attempt_automatic_awakening(p)
        self.assertTrue(awakened["awakened_this_call"])
        self.assertEqual(p.bloodline_tomoe, 1)
        self.assertFalse(kkg.attempt_automatic_awakening(p)["rolled"])

    def test_sharingan_failed_roll_does_not_awaken(self):
        p = Player("Eye", "Eye", level=25)
        p.bloodline_id = "sharingan"
        with patch.object(kkg.random, "random", return_value=0.02):
            self.assertFalse(kkg.attempt_automatic_awakening(p)["awakened_this_call"])
        self.assertFalse(p.bloodline_awakened)

    def test_hyuga_awakens_from_25_at_one_in_300_per_combat_round(self):
        p = Player("Byaku", "Byaku", level=24)
        p.bloodline_id = "byakugan"
        with patch.object(kkg.random, "random", return_value=0):
            self.assertFalse(kkg.attempt_automatic_awakening(p)["rolled"])
        p.level = 25
        with patch.object(kkg.random, "random", return_value=0.005):
            self.assertFalse(kkg.attempt_automatic_awakening(p)["awakened_this_call"])
        with patch.object(kkg.random, "random", return_value=0.003):
            self.assertTrue(kkg.attempt_automatic_awakening(p)["awakened_this_call"])
        self.assertEqual(p.bloodline_tomoe, 0)
        self.assertFalse(kkg.attempt_automatic_awakening(p)["rolled"])

    def test_other_non_eye_bloodline_still_requires_level_50(self):
        p = Player("Kimimaro", "Kimimaro", level=25)
        p.bloodline_id = "shikotsumyaku"
        with patch.object(kkg.random, "random", return_value=0):
            self.assertFalse(kkg.attempt_automatic_awakening(p)["rolled"])
        p.level = 49
        with patch.object(kkg.random, "random", return_value=0):
            self.assertFalse(kkg.attempt_automatic_awakening(p)["rolled"])
        p.level = 50
        with patch.object(kkg.random, "random", return_value=0.003):
            self.assertTrue(kkg.attempt_automatic_awakening(p)["awakened_this_call"])

    def test_high_potential_unlock_rules_are_unchanged(self):
        self.assertEqual(kkg.max_tomoe_for_potential(79), 5)
        self.assertEqual(kkg.max_tomoe_for_potential(80), 6)


if __name__ == "__main__":
    unittest.main()
