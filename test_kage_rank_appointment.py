"""Kage is a manual appointment, not a level-up rank."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import olc
from models import Player


class KageAppointmentTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(player=Player("Admin", "Admin"), send=Mock())
        self.target = Player("Target", "Target", village="leaf",
                             village_rank="chunin", level=100)

    def test_setkage_and_remove_restore_previous_earned_rank(self):
        with (patch.object(olc, "_require_implementor", return_value=True),
              patch.object(olc, "_find_target_player", return_value=(self.target, None)),
              patch("storage.all_players", return_value=[]),
              patch("storage.save_player") as save,
              patch("data_headbands.apply_rank_headband", return_value="Kage Headband"),
              patch("session.ACTIVE_SESSIONS", []),
              patch.object(olc, "_log")):
            olc.cmd_setkage(self.actor, ["Target"])
            self.assertEqual(self.target.village_rank, "kage")
            self.assertEqual(self.target.rank_before_kage, "chunin")
            olc.cmd_setkage(self.actor, ["Target", "remove"])
            self.assertEqual(self.target.village_rank, "chunin")
            self.assertEqual(self.target.rank_before_kage, "")
            self.assertEqual(save.call_count, 2)

    def test_new_kage_replaces_previous_holder_in_same_village(self):
        previous = Player("Previous", "Previous", village="leaf",
                          village_rank="kage", rank_before_kage="special jonin")
        with (patch.object(olc, "_require_implementor", return_value=True),
              patch.object(olc, "_find_target_player", return_value=(self.target, None)),
              patch("storage.all_players", return_value=[previous]),
              patch("storage.save_player") as save,
              patch("data_headbands.apply_rank_headband", return_value="Headband"),
              patch("session.ACTIVE_SESSIONS", []),
              patch.object(olc, "_log")):
            olc.cmd_setkage(self.actor, ["Target"])
        self.assertEqual(previous.village_rank, "special jonin")
        self.assertEqual(self.target.village_rank, "kage")
        self.assertEqual(save.call_count, 2)

    def test_old_kage_without_saved_prior_rank_returns_to_jonin(self):
        self.target.village_rank = "kage"
        self.target.rank_before_kage = ""
        with (patch.object(olc, "_require_implementor", return_value=True),
              patch.object(olc, "_find_target_player", return_value=(self.target, None)),
              patch("storage.save_player"),
              patch("data_headbands.apply_rank_headband", return_value="Headband"),
              patch.object(olc, "_log")):
            olc.cmd_setkage(self.actor, ["Target", "remove"])
        self.assertEqual(self.target.village_rank, "jonin")


if __name__ == "__main__":
    unittest.main()
