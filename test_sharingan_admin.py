"""Mangekyo staff controls and the retired Sharingan technique."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import commands
import data_jutsu
import data_mangekyo
import olc
from models import Player


class SharinganAdminTests(unittest.TestCase):
    def test_mangekyo_rolls_distinct_eyes_once_and_persists(self):
        target = Player(name="Target", account_name="Target")
        target.bloodline_id = "sharingan"
        target.bloodline_awakened = True
        admin = SimpleNamespace(account=SimpleNamespace(staff_level="administrator"),
                                player=SimpleNamespace(name="Admin"), send=lambda message: None)
        with patch.object(olc, "_find_target_player", return_value=(target, None)), \
             patch.object(olc.storage, "save_player") as save, \
             patch.object(olc, "_log"):
            olc._mset_player(admin, "Target", "mangekyo", ["on"])
            self.assertTrue(target.bloodline_mangekyo)
            eyes = target.mangekyo_eye_1, target.mangekyo_eye_2
            self.assertEqual(len(set(eyes)), 2)
            self.assertTrue(all(eye in data_mangekyo.TECHNIQUE_ROSTER for eye in eyes))
            olc.cmd_bloodset(admin, ["Target", "mangekyo", "yes"])
            self.assertEqual((target.mangekyo_eye_1, target.mangekyo_eye_2), eyes)
            self.assertGreaterEqual(save.call_count, 2)

    def test_mangekyo_requires_awakened_sharingan(self):
        target = Player(name="Target", account_name="Target")
        target.bloodline_id = "sharingan"
        admin = SimpleNamespace(account=SimpleNamespace(staff_level="administrator"),
                                player=SimpleNamespace(name="Admin"), send=lambda message: None)
        with patch.object(olc, "_find_target_player", return_value=(target, None)), \
             patch.object(olc.storage, "save_player") as save:
            olc.cmd_bloodset(admin, ["Target", "mangekyo", "yes"])
            self.assertFalse(target.bloodline_mangekyo)
            save.assert_not_called()

    def test_shar_is_same_toggle_and_retired_jutsu_is_absent(self):
        player = Player(name="Target", account_name="Target")
        player.bloodline_id = "sharingan"
        player.bloodline_tomoe = 1
        messages = []
        session = SimpleNamespace(player=player, send=messages.append)
        commands.dispatch_line(session, "shar")
        self.assertTrue(player.sharingan_active)
        commands.dispatch_line(session, "sharingan")
        self.assertFalse(player.sharingan_active)
        self.assertNotIn("sharingan genjutsu", data_jutsu.JUTSU)


if __name__ == "__main__":
    unittest.main()
