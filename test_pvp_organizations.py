"""Organization membership is the gate for every ordinary and special PvP path."""
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import pvp_organizations as orgs
from models import Player


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.one = Player("LeafNinja", "LeafNinja", village="leaf",
                          room_vnum=996001, health=100, maximum_health=100)
        self.two = Player("RogueNinja", "RogueNinja", village="water",
                          room_vnum=996001, health=100, maximum_health=100)
        self.attacker = NS(player=self.one, send=Mock(), pvp_target=None,
                           combat_target=None, pending_cast=None, duel=None)
        self.defender = NS(player=self.two, send=Mock(), pvp_target=None,
                           combat_target=None, pending_cast=None, duel=None)
        self.attacker.active_sessions = lambda: [self.attacker, self.defender]
        self.defender.active_sessions = lambda: [self.attacker, self.defender]
        save = patch.object(orgs.storage, "save_player")
        save.start()
        self.addCleanup(save.stop)

    def test_new_and_legacy_characters_are_not_pvp_enabled(self):
        self.assertEqual(orgs.membership(self.one), "")
        self.assertEqual(Player.from_dict({"name": "Old", "account_name": "Old"}).pvp_organization, "")
        self.assertFalse(orgs.allowed(self.one, self.two))
        self.one.pvp_organization = "invalid"
        self.assertEqual(orgs.membership(self.one), "")

    def test_membership_requires_both_players_and_different_organizations(self):
        self.one.pvp_organization = "anbu"
        self.assertFalse(orgs.allowed(self.one, self.two))
        self.two.pvp_organization = "anbu"
        self.assertFalse(orgs.allowed(self.one, self.two))
        self.two.pvp_organization = "akatsuki"
        self.assertTrue(orgs.allowed(self.one, self.two))
        self.assertTrue(orgs.allowed(self.two, self.one))
        self.assertEqual(orgs.denial_reason(self.one, self.two), "")

    def test_join_and_leave_persist_and_apply_cooldown(self):
        orgs.command(self.attacker, ["join", "anbu"])
        self.assertEqual(self.one.pvp_organization, "anbu")
        self.assertGreater(self.one.pvp_organization_changed_at, 0)
        orgs.command(self.attacker, ["leave"])
        self.assertEqual(self.one.pvp_organization, "anbu")
        self.one.pvp_organization_changed_at = time.time() - orgs.CHANGE_COOLDOWN_SECONDS - 10
        orgs.command(self.attacker, ["leave"])
        self.assertEqual(self.one.pvp_organization, "")
        self.assertFalse(orgs.allowed(self.one, self.two))
        orgs.command(self.attacker, ["join", "root"])
        self.assertEqual(self.one.pvp_organization, "")

    def test_village_restriction_and_unrestricted_akatsuki(self):
        orgs.command(self.defender, ["join", "root"])
        self.assertEqual(self.two.pvp_organization, "")
        orgs.command(self.defender, ["join", "akatsuki"])
        self.assertEqual(self.two.pvp_organization, "akatsuki")

    def test_cannot_leave_while_fighting_or_targeted_by_queued_cast(self):
        self.one.pvp_organization = "anbu"
        self.one.pvp_organization_changed_at = time.time() - 90000
        self.attacker.pvp_target = self.defender
        orgs.command(self.attacker, ["leave"])
        self.assertEqual(self.one.pvp_organization, "anbu")
        self.attacker.pvp_target = None
        self.defender.pending_cast = NS(is_pvp=True, target=self.attacker)
        orgs.command(self.attacker, ["leave"])
        self.assertEqual(self.one.pvp_organization, "anbu")
        self.defender.pending_cast = None
        orgs.command(self.attacker, ["leave"])
        self.assertEqual(self.one.pvp_organization, "")

    def test_cannot_start_direct_player_fight_without_opt_in(self):
        with patch.object(combat.world.WORLD, "get", return_value=NS(safe=False)):
            self.assertFalse(combat.start_pvp_attack(self.attacker, self.defender))
            self.assertFalse(combat.engage_damage_attack(self.attacker, self.two, self.defender))
            self.assertIsNone(self.attacker.pvp_target)
            self.assertIsNone(self.defender.pvp_target)
            self.one.pvp_organization = "root"
            self.two.pvp_organization = "akatsuki"
            self.assertTrue(combat.start_pvp_attack(self.attacker, self.defender))
            self.assertIs(self.attacker.pvp_target, self.defender)
            self.assertIs(self.defender.pvp_target, self.attacker)

    def test_pvp_ends_when_membership_removed_during_live_round(self):
        self.one.pvp_organization = "root"
        self.two.pvp_organization = "akatsuki"
        self.attacker.pvp_target = self.defender
        self.defender.pvp_target = self.attacker
        self.two.pvp_organization = ""
        combat.resolve_pvp_pulse(self.attacker)
        self.assertIsNone(self.attacker.pvp_target)
        self.assertIsNone(self.defender.pvp_target)
        self.assertEqual(self.two.health, 100)

    def test_attack_command_and_duel_protect_regular_players(self):
        with patch.object(commands.combat, "find_mob", return_value=None), \
             patch.object(commands.world.WORLD, "get", return_value=NS(safe=False)):
            commands.cmd_attack(self.attacker, ["RogueNinja"])
            self.assertIsNone(self.attacker.pvp_target)
        commands.cmd_duel(self.attacker, ["RogueNinja"])
        self.assertIsNone(self.attacker.duel)


if __name__ == "__main__":
    unittest.main()
