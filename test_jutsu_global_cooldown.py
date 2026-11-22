"""Regression coverage for the 2s shared cooldown across combat jutsu."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import data_jutsu
import jutsu_global_cooldown as global_cd
from models import Player


class GlobalJutsuCooldownTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("GlobalTester", "GlobalTester", level=100)
        self.player.chakra = 500
        self.player.stamina = 500
        self.messages = []
        self.session = NS(
            player=self.player, send=self.messages.append,
            state=NS(name="PLAYING"),
            pending_cast=None, pending_action=None,
            combat_target=None, pvp_target=None, account=None,
        )
        self.calls = []
        def fake_cast(session, key, target_words):
            self.calls.append((key, tuple(target_words)))
            # Faithfully model the real common combat paths: per-technique
            # cooldown/resource mutation happens only after a valid cast.
            if target_words == ["missing"]:
                session.send("There is nothing here to use that on.")
                return
            now = global_cd.time.time()
            if now < session.player.cooldowns.get(key, 0):
                session.send("That jutsu is still recovering.")
                return
            session.player.chakra -= 10
            session.player.cooldowns[key] = now + 5.0

        p = patch.object(commands, "_cmd_use_jutsu_unlocked", side_effect=fake_cast)
        p.start()
        self.addCleanup(p.stop)

    def test_two_seconds_between_different_jutsu_and_individual_timers_stay(self):
        with patch.object(global_cd.time, "time", return_value=1000.0):
            commands.cmd_use_jutsu(self.session, "dynamic entry", ["enemy"])
        self.assertEqual(self.calls, [("dynamic entry", ("enemy",))])
        self.assertEqual(self.player.cooldowns["dynamic entry"], 1005)
        self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1002)
        chakra = self.player.chakra

        with patch.object(global_cd.time, "time", return_value=1000.6):
            commands.cmd_use_jutsu(self.session, "shadow shuriken technique", ["enemy"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.player.chakra, chakra)
        self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1002)
        self.assertIn("1.4s remaining", self.messages[-1])

        with patch.object(global_cd.time, "time", return_value=1002.0):
            commands.cmd_use_jutsu(self.session, "shadow shuriken technique", ["enemy"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.player.cooldowns["shadow shuriken technique"], 1007)
        self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1004)

        with patch.object(global_cd.time, "time", return_value=1004.0):
            commands.cmd_use_jutsu(self.session, "dynamic entry", ["enemy"])
        # Individual cooldown still blocks this jutsu despite GCD expiry,
        # and the rejected attempt does not start a third GCD.
        self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1004)
        self.assertIn("still recovering", self.messages[-1])

    def test_invalid_target_does_not_start_shared_timer(self):
        with patch.object(global_cd.time, "time", return_value=1100):
            commands.cmd_use_jutsu(self.session, "dynamic entry", ["missing"])
            self.assertNotIn(global_cd.COOLDOWN_KEY, self.player.cooldowns)
            commands.cmd_use_jutsu(self.session, "shadow shuriken technique", ["enemy"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1102)

    def test_shortcuts_perform_and_bare_class_name_share_one_timer(self):
        # Actual command routing is exercised; only the final combat effect
        # is mocked to keep this independent of area/target spawning.
        with patch.object(global_cd.time, "time", return_value=1200.0):
            commands.dispatch_line(self.session, "dyn bandit")
        self.assertEqual(self.calls[-1][0], "dynamic entry")
        with patch.object(global_cd.time, "time", return_value=1200.5):
            commands.dispatch_line(self.session, "perform shadow shuriken technique bandit")
        self.assertEqual(len(self.calls), 1)
        with patch.object(global_cd.time, "time", return_value=1202):
            commands.dispatch_line(self.session, "perform shadow shuriken technique bandit")
        self.assertEqual(self.calls[-1][0], "shadow shuriken technique")
        with patch.object(global_cd.time, "time", return_value=1204):
            commands.dispatch_line(self.session, "choku zuki bandit")
        self.assertEqual(self.calls[-1][0], "choku zuki")

    def test_passives_and_mode_toggles_are_exempt(self):
        for key in ("soto uke", "hidden mist jutsu", "dual wield"):
            self.assertFalse(global_cd.applies(key, []))
        for key in ("dynamic entry", "fireball jutsu",
                    "shadow shuriken technique", "barrier"):
            self.assertTrue(global_cd.applies(key, []))
        with patch.object(global_cd.time, "time", return_value=1300):
            commands.cmd_use_jutsu(self.session, "dynamic entry", ["enemy"])
        with patch.object(global_cd.time, "time", return_value=1300.2):
            commands.cmd_use_jutsu(self.session, "soto uke", [])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1302)

    def test_persistent_timer_survives_player_reload(self):
        with patch.object(global_cd.time, "time", return_value=1400):
            commands.cmd_use_jutsu(self.session, "dynamic entry", ["enemy"])
        restored = Player.from_dict(self.player.to_dict())
        self.session.player = restored
        with patch.object(global_cd.time, "time", return_value=1401):
            commands.cmd_use_jutsu(self.session, "shadow shuriken technique", ["enemy"])
        self.assertEqual(len(self.calls), 1)
        with patch.object(global_cd.time, "time", return_value=1402):
            commands.cmd_use_jutsu(self.session, "shadow shuriken technique", ["enemy"])
        self.assertEqual(len(self.calls), 2)

    def test_pending_handsigns_start_shared_timer_before_resolution(self):
        def start_handsigns(session, key, words):
            session.pending_cast = object()
        with patch.object(commands, "_cmd_use_jutsu_unlocked", side_effect=start_handsigns):
            with patch.object(global_cd.time, "time", return_value=1500):
                commands.cmd_use_jutsu(self.session, "fireball jutsu", ["enemy"])
                self.assertEqual(self.player.cooldowns[global_cd.COOLDOWN_KEY], 1502)
            with patch.object(global_cd.time, "time", return_value=1500.7):
                commands.cmd_use_jutsu(self.session, "dynamic entry", ["enemy"])
        self.assertIn("recover before using another jutsu", self.messages[-1])


if __name__ == "__main__":
    unittest.main()
