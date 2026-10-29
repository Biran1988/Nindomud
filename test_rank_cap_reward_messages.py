"""Capped players retain skill/mission progress without phantom character EXP."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import commands
import leveling
import missions
import skill_training
from models import Player


class RankCappedRewardMessageTests(unittest.TestCase):
    def setUp(self):
        self.player = Player(
            "NoXpTester", "NoXpTester", village="leaf", village_rank="genin",
            level=15, experience=leveling.cumulative_xp_for_level(15),
        )
        self.starting_xp = self.player.experience

    def test_mission_awards_ryo_and_points_but_no_character_exp(self):
        mission = missions.MISSIONS["leaf"][0]
        entry = {"mission_id": mission["mission_id"]}
        self.player.active_missions.append(entry)
        old_ryo = self.player.ryo
        old_mp = self.player.mission_points

        messages = missions._complete_mission(self.player, mission, entry)

        self.assertEqual(self.player.experience, self.starting_xp)
        self.assertEqual(self.player.ryo, old_ryo + mission["reward_ryo"])
        self.assertEqual(self.player.mission_points, old_mp + mission["reward_mission_points"])
        self.assertIn("0 experience", messages[0])
        self.assertIn("Rank cap", messages[0])
        self.assertNotIn("You receive 200 experience", messages[0])

    def test_skill_can_improve_by_use_but_does_not_report_exp(self):
        self.player.learned_skills.append("Strong Fist")
        self.player.skill_proficiencies["Strong Fist"] = 40
        session = SimpleNamespace(player=self.player, send=Mock())
        with patch.object(combat.random, "randint", return_value=1), patch.object(
            skill_training, "needs_first_practice", return_value=False
        ):
            combat.grow_skill_from_usage(self.player, "Strong Fist", session)

        self.assertEqual(self.player.skill_proficiencies["Strong Fist"], 42)
        self.assertEqual(self.player.experience, self.starting_xp)
        output = "\n".join(str(call.args[0]) for call in session.send.call_args_list)
        self.assertIn("improves to 42%", output)
        self.assertNotIn("experience", output.lower())

    def test_teacher_practice_at_cap_does_not_claim_exp(self):
        self.player.learned_skills.append("Strong Fist")
        self.player.skill_proficiencies["Strong Fist"] = 10
        self.player.practice_points = 3
        session = SimpleNamespace(player=self.player, send=Mock())
        with patch.object(commands, "_find_matching_teacher", return_value=object()), patch.object(
            commands, "_practice_gain", return_value=5
        ):
            commands.cmd_practice(session, ["strong", "fist"])

        self.assertEqual(self.player.skill_proficiencies["Strong Fist"], 15)
        self.assertEqual(self.player.experience, self.starting_xp)
        output = "\n".join(str(call.args[0]) for call in session.send.call_args_list)
        self.assertIn("You practice Strong Fist", output)
        self.assertNotIn("experience", output.lower())


if __name__ == "__main__":
    unittest.main()
