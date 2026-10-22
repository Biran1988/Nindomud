"""End-to-end unit coverage of player character deletion and skill gain XP.

These assertions use isolated temporary account files; they never touch
the live MUD's player data or builder-created world/area state.
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import commands
import leveling
import security
import storage
from models import Account, Player


class SkillImprovementXpTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("SkillXptest", "SkillXptest")
        self.player.learned_skills = ["Sword", "Dynamic Entry"]
        self.player.skill_proficiencies = {"Sword": 50, "Dynamic Entry": 0}
        self.player.practice_points = 4
        self.player.intelligence = 10
        self.session = SimpleNamespace(player=self.player, send=Mock())

    def test_practice_awards_ten_xp_for_each_real_percentage_point(self):
        before = self.player.experience
        with patch.object(commands, "_find_matching_teacher", return_value=object()):
            commands.cmd_practice(self.session, ["dynamic", "entry"])
        percentage = self.player.skill_proficiencies["Dynamic Entry"]
        self.assertGreater(percentage, 0)
        self.assertEqual(self.player.experience - before, percentage * 10)
        self.assertIn("experience from skill improvement",
                      " ".join(c.args[0] for c in self.session.send.call_args_list))

    def test_combat_use_awards_xp_and_visible_feedback(self):
        before = self.player.experience
        with patch.object(combat.random, "randint", return_value=1):
            combat.grow_skill_from_usage(self.player, "Sword", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Sword"], 52)
        self.assertEqual(self.player.experience - before, 20)
        self.assertIn("+20 experience",
                      " ".join(c.args[0] for c in self.session.send.call_args_list))

    def test_sword_at_seven_percent_improves_from_usage(self):
        self.player.skill_proficiencies["Sword"] = 7
        before = self.player.experience
        with patch.object(combat.random, "randint", return_value=50):
            combat.grow_skill_from_usage(self.player, "Sword", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Sword"], 9)
        self.assertEqual(self.player.experience - before, 20)
        self.assertIn("Sword improves to 9%", " ".join(
            c.args[0] for c in self.session.send.call_args_list))

    def test_usage_roll_can_fail_even_below_teacher_cap(self):
        self.player.skill_proficiencies["Sword"] = 7
        with patch.object(combat.random, "randint", return_value=100):
            combat.grow_skill_from_usage(self.player, "Sword", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Sword"], 7)
        self.assertEqual(self.player.experience, 0)

    def test_low_proficiency_jutsu_also_improves_from_usage(self):
        self.player.skill_proficiencies["Dynamic Entry"] = 3
        with patch.object(combat.random, "randint", return_value=50):
            combat.grow_skill_from_usage(self.player, "Dynamic Entry", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Dynamic Entry"], 5)
        self.assertEqual(self.player.experience, 20)

    def test_unlearned_skill_does_not_improve(self):
        with patch.object(combat.random, "randint", return_value=1):
            combat.grow_skill_from_usage(self.player, "Unlearned", session=self.session)
        self.assertNotIn("Unlearned", self.player.skill_proficiencies)
        self.assertEqual(self.player.experience, 0)

    def test_no_xp_when_skill_does_not_improve_or_is_capped(self):
        self.player.skill_proficiencies["Sword"] = 100
        combat.grow_skill_from_usage(self.player, "Sword", session=self.session)
        self.assertEqual(self.player.experience, 0)
        self.player.skill_proficiencies["Sword"] = 98
        with patch.object(combat.random, "randint", return_value=100):
            combat.grow_skill_from_usage(self.player, "Sword", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Sword"], 98)
        self.assertEqual(self.player.experience, 0)

    def test_last_percentage_point_awards_only_ten_xp(self):
        self.player.skill_proficiencies["Sword"] = 99
        with patch.object(combat.random, "randint", return_value=1):
            combat.grow_skill_from_usage(self.player, "Sword", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Sword"], 100)
        self.assertEqual(self.player.experience, 10)


class SelfDeleteCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = self.temp.name
        for attr, suffix in (("DATA_DIR", ""), ("ACCOUNTS_DIR", "accounts"),
                             ("PLAYERS_DIR", "players")):
            p = patch.object(storage, attr, os.path.join(base, suffix))
            p.start()
            self.addCleanup(p.stop)
        self.password = "ActualPassword123"
        salt, digest = security.hash_password(self.password)
        self.account = Account("Deletetest", salt, digest)
        self.player = Player("Deletetest", "Deletetest")
        storage.save_account(self.account)
        storage.save_player(self.player)
        self.session = SimpleNamespace(account=self.account, player=self.player,
                                       send=Mock(), request_close=Mock())

    def test_delete_requires_both_passwords_and_destroys_both_files(self):
        commands.dispatch(self.session, "delete",
                          [self.password, self.password])
        self.assertFalse(storage.account_exists("Deletetest"))
        self.assertFalse(storage.player_exists("Deletetest"))
        self.session.request_close.assert_called_once()
        self.assertIn("permanently deleted",
                      self.session.send.call_args.args[0])

    def test_wrong_password_and_mismatch_leave_both_files_intact(self):
        for args in (
            ["WrongPassword123", "WrongPassword123"],
            [self.password, "WrongPassword123"],
            [],
        ):
            commands.dispatch(self.session, "delete", args)
            self.assertTrue(storage.account_exists("Deletetest"))
            self.assertTrue(storage.player_exists("Deletetest"))
        self.session.request_close.assert_not_called()

    def test_staff_cannot_self_delete(self):
        self.account.staff_level = "implementor"
        commands.dispatch(self.session, "delete",
                          [self.password, self.password])
        self.assertTrue(storage.account_exists("Deletetest"))
        self.assertTrue(storage.player_exists("Deletetest"))
        self.session.request_close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
