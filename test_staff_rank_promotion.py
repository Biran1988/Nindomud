"""Immortal PROMOTE takes exactly one ninja rank step."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import kage
import staff_rank_promotion
from models import Player


class ImmortalPromoteTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(account=NS(name="Helper", staff_level="helper"),
                        player=Player("Helper", "Helper"),
                        send=Mock())
        self.target = Player("Target", "Target", village="leaf",
                             village_rank="student", mission_points=0)
        self.live = NS(player=self.target, send=Mock())

    def invoke(self):
        with (patch("olc._find_target_player", return_value=(self.target, self.live)),
              patch("storage.save_player") as save,
              patch("data_headbands.apply_rank_headband", return_value="New Headband") as head,
              patch.object(kage, "announce_rank_up") as announcement,
              patch("olc._log")):
            staff_rank_promotion.command(self.actor, ["Target"])
            return save, head, announcement

    def test_student_to_genin_one_step_with_headband_and_mission_points(self):
        save, head, announcement = self.invoke()
        self.assertEqual(self.target.village_rank, "genin")
        self.assertEqual(self.target.mission_points, 50)
        self.assertEqual(self.target.mission_points_earned_total, 50)
        head.assert_called_once_with(self.target, "genin")
        save.assert_called_once_with(self.target)
        announcement.assert_called_once_with("Target", "genin")

    def test_mid_ladder_advances_exactly_one_even_without_level_requirements(self):
        self.target.village_rank = "chunin"
        save, _, _ = self.invoke()
        self.assertEqual(self.target.village_rank, "special jonin")
        save.assert_called_once_with(self.target)

    def test_promote_stops_at_jonin_even_for_implementor(self):
        self.target.village_rank = "jonin"
        self.actor.account.name = "biran"
        self.actor.account.staff_level = "implementor"
        with patch("olc.cmd_setkage") as appoint:
            save, _, _ = self.invoke()
        self.assertEqual(self.target.village_rank, "jonin")
        self.assertFalse(save.called)
        appoint.assert_not_called()

    def test_player_rank_cannot_use_immortal_promotion(self):
        self.actor.account.staff_level = "player"
        self.invoke()
        self.assertEqual(self.target.village_rank, "student")

    def test_command_is_separate_from_promoteimm(self):
        self.assertIs(commands.COMMANDS["promote"], staff_rank_promotion.command)
        self.assertIsNot(commands.COMMANDS["promote"], commands.cmd_promoteimm)


if __name__ == "__main__":
    unittest.main()
