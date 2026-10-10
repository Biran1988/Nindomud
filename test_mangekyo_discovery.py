"""Staff testing and per-eye help discovery use authenticated accounts."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import help_system
import mangekyo_discovery
import status_effects
from models import Account, Player
from session import State


class MangekyoDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("EyeTester", "EyeTester", chakra=500, maximum_chakra=500)
        self.session = NS(player=self.player, account=Account("EyeTester", "", ""),
                          send=Mock(), pending_cast=None, state=State.PLAYING)

    def test_staff_access_needs_authenticated_live_session(self):
        technique = data_jutsu.JUTSU["kamui intangibility"]
        with patch("session.ACTIVE_SESSIONS", [self.session]), patch("storage.save_player"):
            self.assertFalse(combat._can_use_jutsu(self.player, technique, "kamui intangibility"))
            self.session.account.staff_level = "builder"
            self.assertTrue(combat._can_use_jutsu(self.player, technique, "kamui intangibility"))
            commands.cmd_use_jutsu(self.session, "kamui intangibility", [])
            self.assertGreater(self.player.kamui_intangibility_rounds_left, 0)
            commands.cmd_izanagi(self.session, [])
            self.assertTrue(self.player.izanagi_active)
            self.assertTrue(combat.try_trigger_izanagi(self.session))
            self.assertEqual(self.player.health, self.player.maximum_health)
        self.assertFalse(combat._can_use_jutsu(self.player, technique, "kamui intangibility"))

    def test_help_unlocks_only_used_assigned_eye_and_persists(self):
        self.player.bloodline_id = "sharingan"
        self.player.bloodline_mangekyo = True
        self.player.mangekyo_eye_1 = "kamui"
        self.player.mangekyo_eye_2 = "tsukuyomi"
        kamui = {"primary_keyword": "kamui limb removal"}
        tsukuyomi = {"primary_keyword": "tsukuyomi"}
        action = {"primary_keyword": "stab"}
        other_eye = {"primary_keyword": "amaterasu"}
        self.assertFalse(mangekyo_discovery.can_read(self.session, kamui))
        with patch("storage.save_player") as save:
            mangekyo_discovery.record_use(self.player, "kamui intangibility")
            mangekyo_discovery.record_use(self.player, "kamui pocket dimension")
            save.assert_called_once_with(self.player)
        self.assertTrue(mangekyo_discovery.can_read(self.session, kamui))
        self.assertFalse(mangekyo_discovery.can_read(self.session, tsukuyomi))
        self.assertFalse(mangekyo_discovery.can_read(self.session, action))
        self.assertFalse(mangekyo_discovery.can_read(self.session, other_eye))
        self.assertEqual(Player.from_dict(self.player.to_dict()).mangekyo_eyes_used, ["kamui"])
        self.session.account.staff_level = "builder"
        self.assertTrue(mangekyo_discovery.can_read(self.session, other_eye))
        self.session.account.staff_level = "player"
        self.player.bloodline_mangekyo = False
        self.assertFalse(mangekyo_discovery.can_read(self.session, kamui))

    def test_help_index_and_shortcuts_hide_undiscovered_eyes(self):
        entries = [dict(primary_keyword="amaterasu", keywords=["amaterasu"], title="Amaterasu", body="secret"),
                   dict(primary_keyword="barrier", keywords=["barrier"], title="Barrier", body="public")]
        with patch.object(help_system, "all_entries", return_value=entries):
            help_system.cmd_help(self.session, ["amaterasu"])
            self.session.send.assert_called_with("This helpfile doesn't exist, contact an admin to create it.")
            self.session.send.reset_mock()
            help_system.cmd_help(self.session, [])
            text = self.session.send.call_args.args[0]
            self.assertIn("barrier", text)
            self.assertNotIn("amaterasu", text)
            self.session.send.reset_mock()
            self.player.bloodline_id = "sharingan"
            self.player.bloodline_mangekyo = True
            self.player.mangekyo_eye_1 = "amaterasu"
            with patch("storage.save_player"):
                mangekyo_discovery.record_use(self.player, "amaterasu")
            help_system.cmd_help(self.session, ["amaterasu"])
            self.assertIn("secret", self.session.send.call_args.args[0])

    def test_genjutsu_duration_preserves_other_status_sources(self):
        self.assertEqual(status_effects.genjutsu_duration("stunned"), 10)
        effects = {}
        status_effects.apply_effect(effects, "stunned", source="ordinary")
        self.assertEqual(effects["stunned"]["duration"], 1)
        status_effects.apply_effect(effects, "stunned", source="jubaku satsu",
                                    duration_override=status_effects.genjutsu_duration("stunned"))
        self.assertEqual(effects["stunned"]["duration"], 10)


if __name__ == "__main__":
    unittest.main()
