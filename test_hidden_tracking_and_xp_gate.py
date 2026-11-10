"""Regressions for standalone hidden exits, Track tiers, and XP carryover."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import commands
import leveling
import tracking
import world
from models import Player


class HiddenExitTrackingTests(unittest.TestCase):
    def setUp(self):
        self.rooms = {
            900001: world.Room(900001, "Approach", "A mountain trail."),
            900002: world.Room(900002, "Secret Passage", "A dark tunnel."),
            900003: world.Room(900003, "Sanctuary", "A distant room."),
        }
        self.rooms[900001].exits["north"] = 900002
        self.rooms[900002].exits["south"] = 900001
        self.rooms[900002].exits["east"] = 900003
        self.rooms[900001].exit_flags["north"] = ["hidden"]
        self.fake_world = NS(WORLD=NS(get=self.rooms.get))
        self.area = NS(name="Test Area", vnum_start=900001, vnum_end=900003)

    def test_hidden_exit_is_a_real_passage_without_a_door(self):
        start = self.rooms[900001]
        self.assertNotIn("door", start.exit_flags["north"])
        self.assertNotIn("North", commands._format_exits(start, False)[0])
        self.assertIn("North (hidden)", commands._format_exits(start, True)[0])
        self.assertFalse(tracking._room_exits_are_passable(start, "north"))
        self.assertTrue(tracking._room_exits_are_passable(start, "north", allow_hidden=True))

    def test_old_track_and_advanced_track_cannot_use_hidden_passage(self):
        self.assertIsNone(tracking.find_path(
            self.fake_world, 900001, 900003, self.area))
        self.assertIsNone(tracking.find_path(
            self.fake_world, 900001, 900003, None))
        self.assertEqual(tracking.find_path(
            self.fake_world, 900001, 900003, None, allow_hidden=True),
            ["north", "east"])

    def test_hidden_tracking_unlock_requires_level_50_and_the_skill(self):
        player = Player("Scout", "Scout", level=49, village_rank="elite jonin")
        player.learned_skills = ["Track", "Advanced Tracking", "Hidden Tracking"]
        self.assertFalse(tracking.has_hidden_tracking(player))
        player.level = 50
        self.assertTrue(tracking.has_hidden_tracking(player))
        player.learned_skills.remove("Hidden Tracking")
        self.assertFalse(tracking.has_hidden_tracking(player))

    def test_secret_tracking_cannot_open_a_closed_door(self):
        room = self.rooms[900001]
        room.exit_flags["north"] = ["hidden", "door"]
        room.exit_door_open["north"] = False
        self.assertIsNone(tracking.find_path(
            self.fake_world, 900001, 900003, None, allow_hidden=True))
        room.exit_door_open["north"] = True
        self.assertEqual(tracking.find_path(
            self.fake_world, 900001, 900003, None, allow_hidden=True),
            ["north", "east"])


class ExperienceCarryoverTests(unittest.TestCase):
    """Large rewards retain surplus XP and can award several levels."""

    def character(self, level=50):
        player = Player("LevelTester", "LevelTester", level=level,
                        village_rank="elite jonin", primary_class="taijutsu")
        player.experience = leveling.cumulative_xp_for_level(level)
        return player

    def award(self, player, amount):
        with patch.object(leveling.storage, "save_player"), patch.object(
                leveling.shinobi_notices, "announce_level"):
            return leveling.grant_experience(player, amount)

    def test_single_kill_overflow_is_saved_toward_following_level(self):
        player = self.character()
        player.experience = leveling.xp_for_next_level(50) - 200_000
        messages = self.award(player, 500_000)
        self.assertEqual(player.level, 51)
        self.assertEqual(player.experience, leveling.cumulative_xp_for_level(51) + 300_000)
        self.assertTrue(any("reached level 51" in line for line in messages))

    def test_single_large_reward_can_gain_multiple_levels(self):
        player = self.character(level=20)
        amount = leveling.cumulative_xp_for_level(24) - player.experience
        self.award(player, amount)
        self.assertEqual(player.level, 24)
        self.assertEqual(player.experience, leveling.cumulative_xp_for_level(24))

    def test_existing_progress_and_incomplete_rewards_are_retained(self):
        player = self.character(level=50)
        player.experience += 150_000
        self.award(player, 500_000)
        self.assertEqual(player.level, 50)
        self.assertEqual(player.experience, leveling.cumulative_xp_for_level(50) + 650_000)

    def test_endgame_xp_tax_still_applies_to_multiple_bands(self):
        player = self.character(level=225)
        band = leveling.xp_band_for_level(225)
        self.award(player, (band * 150 + 99) // 100 + 1_000_000)
        self.assertEqual(player.level, 226)
        self.assertGreater(player.experience, leveling.cumulative_xp_for_level(226))


if __name__ == "__main__":
    unittest.main()
