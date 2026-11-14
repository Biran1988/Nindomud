"""Mastery grind is 3x the former effort across practice and regular use."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import skill_training
from models import Player


class MasteryEffortMultiplierTests(unittest.TestCase):
    def test_mastery_roll_uses_three_times_the_previous_range(self):
        self.assertEqual(skill_training.MASTERY_EFFORT_MULTIPLIER, 3)
        for roll, expected in ((1, True), (50, True), (51, False), (300, False)):
            with self.subTest(roll=roll), patch.object(skill_training.random, "randint", return_value=roll) as rng:
                self.assertEqual(skill_training.mastery_gain_roll(50), expected)
                rng.assert_called_once_with(1, 300)

    def test_chance_over_100_is_clamped_to_old_guaranteed_rate(self):
        # Signature mastery formerly could be guaranteed below 50%; now
        # that guaranteed roll is one-third of all attempts.
        with patch.object(skill_training.random, "randint", return_value=101):
            self.assertFalse(skill_training.mastery_gain_roll(150))
        with patch.object(skill_training.random, "randint", return_value=100):
            self.assertTrue(skill_training.mastery_gain_roll(150))

    def test_practice_gain_is_one_third_of_previous_for_divisible_intelligence(self):
        player = Player("Student", "Student")
        player.intelligence = 36
        self.assertEqual(commands._practice_gain(player), 6)  # old: 18
        player.intelligence = 6
        self.assertEqual(commands._practice_gain(player), 1)

    def test_weapon_and_jutsu_both_use_slowdown(self):
        player = Player("Tester", "Tester")
        player.learned_skills = ["Sword", "Dynamic Entry"]
        player.skill_proficiencies = {"Sword": 50, "Dynamic Entry": 50}
        session = NS(player=player, send=Mock())
        with patch.object(skill_training.random, "randint", return_value=51):
            for name in player.learned_skills:
                combat.grow_skill_from_usage(player, name, session)
        self.assertEqual(player.skill_proficiencies, {"Sword": 50, "Dynamic Entry": 50})
        with patch.object(skill_training.random, "randint", return_value=50):
            for name in player.learned_skills:
                combat.grow_skill_from_usage(player, name, session)
        self.assertEqual(player.skill_proficiencies, {"Sword": 52, "Dynamic Entry": 52})


if __name__ == "__main__":
    unittest.main()
