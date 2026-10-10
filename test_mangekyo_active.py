"""Mangekyo use requires the Sharingan toggle throughout casting."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
from models import Player
from session import State


class MangekyoActiveTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Eye", "Eye", chakra=500, maximum_chakra=500)
        self.player.bloodline_id = "sharingan"
        self.player.bloodline_mangekyo = True
        self.player.bloodline_tomoe = 6
        self.session = NS(player=self.player, send=Mock(), pending_cast=None,
                          state=State.PLAYING)

    def test_every_assigned_eye_technique_needs_active_sharingan(self):
        for key, jutsu in data_jutsu.JUTSU.items():
            if jutsu.get("kkg_gate") != "mangekyo_technique":
                continue
            self.player.mangekyo_eye_1 = jutsu.get("mangekyo_roster_key", key)
            self.player.sharingan_active = False
            self.player.copied_jutsu_key = key
            self.assertFalse(combat._can_use_jutsu(self.player, jutsu, key), key)
            commands.cmd_use_jutsu(self.session, key, [])
            self.session.send.assert_called_with("Activate your Sharingan before using Mangekyo techniques.")
            self.assertEqual(self.player.chakra, 500)
            self.player.sharingan_active = True
            self.assertTrue(combat._can_use_jutsu(self.player, jutsu, key), key)
            self.player.bloodline_mangekyo = False
            self.assertFalse(combat._can_use_jutsu(self.player, jutsu, key), key)
            self.player.bloodline_mangekyo = True
            self.player.copied_jutsu_key = None

    def test_izanagi_cannot_activate_or_trigger_with_sharingan_off(self):
        self.player.mangekyo_eye_1 = "izanagi"
        commands.cmd_izanagi(self.session, [])
        self.assertFalse(self.player.izanagi_active)
        self.session.send.assert_called_with("Activate your Sharingan before using Mangekyo techniques.")
        self.player.sharingan_active = True
        commands.cmd_izanagi(self.session, [])
        self.assertTrue(self.player.izanagi_active)
        self.player.sharingan_active = False
        self.assertFalse(combat.try_trigger_izanagi(self.session))
        self.assertTrue(self.player.izanagi_active)
        commands.cmd_izanagi(self.session, [])
        self.assertFalse(self.player.izanagi_active)

    def test_delayed_cast_fizzles_if_sharingan_fades(self):
        self.player.mangekyo_eye_1 = "amaterasu"
        self.player.sharingan_active = False
        self.session.pending_cast = combat.PendingCast("amaterasu", NS(player=Player("Target", "Target")), True, 1)
        with patch("session.ACTIVE_SESSIONS", [self.session]), patch.object(combat, "_check_jutsu_collisions"):
            combat.tick_pending_casts()
        self.assertIsNone(self.session.pending_cast)
        self.session.send.assert_called_with(
            "&RYour Sharingan is no longer active -- the Mangekyo technique fades before it takes hold.&x")


if __name__ == "__main__":
    unittest.main()
