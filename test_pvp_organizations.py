"""Opt-in PvP organizations: protected nonmembers and rival-only consensual duels."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import duel
import pvp_organizations as org
from models import Player


class OrganizationPvPTests(unittest.TestCase):
    def make_session(self, name, *, village="leaf", faction="", room=100500):
        player = Player(name, name, village=village, room_vnum=room)
        player.pvp_organization = faction
        s = NS(player=player, pvp_target=None, combat_target=None,
               duel=None, pending_cast=None, send=Mock(),
               state=NS(name="PLAYING"))
        return s

    def setUp(self):
        self.first = self.make_session("First")
        self.second = self.make_session("Second")
        self.first.active_sessions = lambda: [self.first, self.second]
        self.second.active_sessions = self.first.active_sessions
        self.patch_room = patch.object(combat.world.WORLD, "get", return_value=NS(safe=False))
        self.patch_room.start()
        self.addCleanup(self.patch_room.stop)

    def test_nonmembers_cannot_attack_or_be_attacked(self):
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.assertIsNone(self.first.pvp_target)
        self.first.player.pvp_organization = "anbu"
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.assertIsNone(self.second.pvp_target)

    def test_rivals_can_fight_but_organization_allies_cannot(self):
        self.first.player.pvp_organization = "anbu"
        self.second.player.pvp_organization = "anbu"
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.second.player.pvp_organization = "root"
        self.assertTrue(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.assertIs(self.first.pvp_target, self.second)
        self.assertIs(self.second.pvp_target, self.first)

    def test_formal_duel_cannot_bypass_membership_requirements(self):
        fight = duel.start_duel(self.first, self.second)
        self.assertFalse(org.allowed_sessions(self.first, self.second))
        fight.accepted = True
        self.assertFalse(org.allowed_sessions(self.first, self.second))
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.assertIsNone(self.first.pvp_target)

    def test_formal_duel_does_not_permit_friendly_fire(self):
        self.first.player.pvp_organization = "root"
        self.second.player.pvp_organization = "root"
        fight = duel.start_duel(self.first, self.second)
        fight.accepted = True
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))

    def test_duel_command_rejects_unaffiliated_and_allied_players(self):
        commands.cmd_duel(self.first, ["Second"])
        self.assertIsNone(self.first.duel)
        self.first.player.pvp_organization = "root"
        commands.cmd_duel(self.first, ["Second"])
        self.assertIsNone(self.first.duel)
        self.second.player.pvp_organization = "root"
        commands.cmd_duel(self.first, ["Second"])
        self.assertIsNone(self.first.duel)

    def test_duel_command_allows_rivals_to_challenge_and_accept(self):
        self.first.player.pvp_organization = "anbu"
        self.second.player.pvp_organization = "root"
        commands.cmd_duel(self.first, ["Second"])
        self.assertIs(self.first.duel, self.second.duel)
        self.assertFalse(self.first.duel.accepted)
        with patch("duel.begin_duel"):
            commands.cmd_duel(self.second, ["First"])
        self.assertTrue(self.first.duel.accepted)

    def test_safe_room_still_blocks_rival_duel_attacks(self):
        self.first.player.pvp_organization = "anbu"
        self.second.player.pvp_organization = "root"
        fight = duel.start_duel(self.first, self.second)
        fight.accepted = True
        with patch.object(combat.world.WORLD, "get", return_value=NS(safe=True)):
            self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))

    def test_join_leave_changes_affiliation_without_changing_clan(self):
        self.first.player.clan = "uchiha"
        with patch.object(org.storage, "save_player") as save, patch.object(org.time, "time", return_value=2000000000):
            org.command(self.first, ["join", "anbu"])
            self.assertEqual(self.first.player.pvp_organization, "anbu")
            self.assertEqual(self.first.player.clan, "uchiha")
            save.assert_called()
            org.command(self.first, ["leave"])
            self.assertEqual(self.first.player.pvp_organization, "anbu")  # cooldown
            with patch.object(org.time, "time", return_value=2000000000 + 86401):
                org.command(self.first, ["leave"])
                self.assertEqual(self.first.player.pvp_organization, "")

    def test_village_requirement_and_save_round_trip(self):
        outsider = self.make_session("Outsider", village="water")
        outsider.active_sessions = lambda: [outsider]
        with patch.object(org.storage, "save_player"):
            org.command(outsider, ["join", "anbu"])
            self.assertEqual(outsider.player.pvp_organization, "")
            org.command(outsider, ["join", "akatsuki"])
            self.assertEqual(outsider.player.pvp_organization, "akatsuki")
        restored = Player.from_dict(outsider.player.to_dict())
        self.assertEqual(restored.pvp_organization, "akatsuki")
        self.assertEqual(Player("New", "New").pvp_organization, "")


if __name__ == "__main__":
    unittest.main()
