"""Kage is an appointment independent from earned rank and level caps."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import kage
import leveling
import olc
from models import Player


class KageAppointmentTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(player=Player("Admin", "Admin"), send=Mock())
        self.target = Player("Target", "Target", village="leaf",
                             village_rank="chunin", level=65)

    def test_setkage_and_remove_keep_earned_rank(self):
        with (patch.object(olc, "_require_implementor", return_value=True),
              patch.object(olc, "_find_target_player", return_value=(self.target, None)),
              patch("storage.all_players", return_value=[]),
              patch("storage.save_player") as save,
              patch("data_headbands.apply_rank_headband", return_value="Headband") as band,
              patch("session.ACTIVE_SESSIONS", []),
              patch.object(olc, "_log")):
            olc.cmd_setkage(self.actor, ["Target"])
            self.assertTrue(self.target.is_kage)
            self.assertEqual(self.target.village_rank, "chunin")
            self.assertEqual(leveling.rank_level_cap(self.target), 65)
            self.assertEqual(kage.display_rank(self.target), "Chunin (Kage)")
            olc.cmd_setkage(self.actor, ["Target", "remove"])
            self.assertFalse(self.target.is_kage)
            self.assertEqual(self.target.village_rank, "chunin")
            self.assertEqual(save.call_count, 2)
            self.assertEqual([x.args[1] for x in band.call_args_list], ["kage", "chunin"])

    def test_replacement_is_limited_to_own_village(self):
        old = Player("Old", "Old", village="leaf",
                     village_rank="special jonin", is_kage=True)
        other = Player("Other", "Other", village="sand",
                       village_rank="jonin", is_kage=True)
        with (patch.object(olc, "_require_implementor", return_value=True),
              patch.object(olc, "_find_target_player", return_value=(self.target, None)),
              patch("storage.all_players", return_value=[old, other]),
              patch("storage.save_player") as save,
              patch("data_headbands.apply_rank_headband", return_value="Headband"),
              patch("session.ACTIVE_SESSIONS", []),
              patch.object(olc, "_log")):
            olc.cmd_setkage(self.actor, ["Target"])
        self.assertFalse(old.is_kage)
        self.assertEqual(old.village_rank, "special jonin")
        self.assertTrue(other.is_kage)
        self.assertTrue(self.target.is_kage)
        self.assertEqual(save.call_count, 2)

    def test_ordinary_promotion_does_not_strip_kage_headband(self):
        import data_headbands
        p = Player("Appointed", "Appointed", village="leaf",
                   village_rank="chunin", level=65, is_kage=True,
                   completed_missions=list(range(50)))
        with patch.object(data_headbands, "apply_rank_headband", wraps=data_headbands.apply_rank_headband) as band, \
             patch("commands._apply_equipment_stat_bonuses"), \
             patch.object(kage, "announce_rank_up"):
            message = kage.handle_promotion_request(p)
        self.assertIn("promoted to Special Jonin", message)
        self.assertTrue(p.is_kage)
        self.assertEqual(p.village_rank, "special jonin")
        self.assertEqual(p.equipment["head"], "A Konoha Kage's Headband")
        band.assert_called_once_with(p, "special jonin")

    def test_old_kage_saved_rank_migrates_safely(self):
        for previous, expected in (("chunin", "chunin"), ("", "jonin"),
                                   ("village elder", "jonin")):
            with self.subTest(previous=previous):
                old = Player("Old", "Old", village="leaf",
                             village_rank="kage", rank_before_kage=previous)
                loaded = Player.from_dict(old.to_dict())
                self.assertTrue(loaded.is_kage)
                self.assertEqual(loaded.village_rank, expected)
                self.assertEqual(loaded.rank_before_kage, "")


if __name__ == "__main__":
    unittest.main()
