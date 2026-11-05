"""Immortal Mangekyo OFF/ON must discard old eye powers and reroll."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import data_mangekyo
import olc
from models import Player


class MangekyoBloodsetRerollTests(unittest.TestCase):
    def setUp(self):
        self.target = Player("TestUchiha", "TestUchiha")
        self.target.bloodline_id = "sharingan"
        self.target.bloodline_awakened = True
        self.target.bloodline_tomoe = 6
        self.target.bloodline_mangekyo = True
        self.target.mangekyo_eye_1 = "kamui"
        self.target.mangekyo_eye_2 = "izanagi"
        self.target.mangekyo_eyes_used = ["kamui", "izanagi"]
        self.target.izanagi_active = True
        self.target.kamui_intangibility_rounds_left = 3
        self.staff = NS(account=NS(staff_level="implementor"),
                        player=NS(name="Admin"), send=Mock())
        self.saved = []
        patches = (
            patch.object(olc, "_require_admin", return_value=True),
            patch.object(olc, "_find_target_player", return_value=(self.target, None)),
            patch.object(olc.storage, "save_player",
                         side_effect=lambda p: self.saved.append(p.to_dict())),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def command(self, state):
        olc.cmd_bloodset(self.staff, ["TestUchiha", "mangekyo", state])

    def test_off_erases_assigned_eyes_and_discovery_and_saves(self):
        self.command("no")
        self.assertFalse(self.target.bloodline_mangekyo)
        self.assertEqual((self.target.mangekyo_eye_1, self.target.mangekyo_eye_2),
                         (None, None))
        self.assertEqual(self.target.mangekyo_eyes_used, [])
        self.assertEqual(self.target.mangekyo_previous_eyes, ["kamui", "izanagi"])
        self.assertFalse(self.target.izanagi_active)
        self.assertEqual(self.target.kamui_intangibility_rounds_left, 0)
        self.assertEqual(self.target.bloodline_id, "sharingan")
        self.assertTrue(self.target.bloodline_awakened)
        self.assertEqual(self.target.bloodline_tomoe, 6)
        self.assertEqual(self.saved[-1]["mangekyo_eye_1"], None)
        self.assertIn("cleared", self.staff.send.call_args.args[0].lower())

    def test_on_gives_two_different_new_eyes_after_save_reload(self):
        self.command("off")
        # Simulate a player save reload or server reboot between staff toggles.
        self.target = Player.from_dict(self.saved[-1])
        self.command("on")
        new_eyes = (self.target.mangekyo_eye_1, self.target.mangekyo_eye_2)
        self.assertTrue(self.target.bloodline_mangekyo)
        self.assertEqual(len(set(new_eyes)), 2)
        self.assertTrue(set(new_eyes).isdisjoint({"kamui", "izanagi"}))
        self.assertTrue(set(new_eyes) <= set(data_mangekyo.TECHNIQUE_ROSTER))
        self.assertEqual(self.target.mangekyo_eyes_used, [])
        self.assertEqual(Player.from_dict(self.saved[-1]).mangekyo_eye_1, new_eyes[0])

    def test_repeated_yes_keeps_current_pair_but_off_always_clears(self):
        with patch.object(data_mangekyo, "roll_two_eye_techniques") as roll:
            self.command("yes")
            self.assertEqual((self.target.mangekyo_eye_1, self.target.mangekyo_eye_2),
                             ("kamui", "izanagi"))
            roll.assert_not_called()
        self.command("no")
        self.command("no")
        self.assertEqual(self.target.mangekyo_previous_eyes, ["kamui", "izanagi"])
        self.command("yes")
        self.assertEqual(self.target.mangekyo_eyes_used, [])
        self.assertTrue(set((self.target.mangekyo_eye_1, self.target.mangekyo_eye_2))
                        .isdisjoint({"kamui", "izanagi"}))

    def test_normal_new_user_roll_still_draws_from_entire_roster(self):
        with patch.object(data_mangekyo.random, "sample", return_value=["kamui", "izanagi"]) as sample:
            self.assertEqual(data_mangekyo.roll_two_eye_techniques(), ("kamui", "izanagi"))
            sample.assert_called_once_with(list(data_mangekyo.TECHNIQUE_ROSTER), 2)

    def test_bloodset_rejects_enable_without_awakened_sharingan(self):
        self.target.bloodline_awakened = False
        self.command("no")
        self.command("yes")
        self.assertFalse(self.target.bloodline_mangekyo)
        self.assertIsNone(self.target.mangekyo_eye_1)
        self.assertIn("requires", self.staff.send.call_args.args[0].lower())


if __name__ == "__main__":
    unittest.main()
