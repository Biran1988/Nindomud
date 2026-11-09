"""Regression coverage for invite-only organizations and open consensual duels."""
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import duel
import organization_leaders as leadership
import pvp_organizations as org
from models import Player


class OrganizationPvPTests(unittest.TestCase):
    def make(self, name, village="leaf"):
        s = NS(player=Player(name, name, village=village, room_vnum=100500),
               account=NS(staff_level="player"), pvp_target=None,
               combat_target=None, pending_cast=None, duel=None, send=Mock(),
               state=NS(name="PLAYING"))
        s.active_sessions = lambda: [self.first, self.second]
        return s

    def setUp(self):
        self.first = self.make("First")
        self.second = self.make("Second")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(leadership.storage, "DATA_DIR", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(leadership.storage, "save_player")
        self.save = p.start()
        self.addCleanup(p.stop)
        p = patch.object(combat.world.WORLD, "get", return_value=NS(safe=False))
        p.start()
        self.addCleanup(p.stop)

    def appoint(self, key="anbu", name="First"):
        self.first.account.staff_level = "implementor"
        org.command(self.first, ["appoint", key, name])
        self.first.account.staff_level = "player"

    def test_default_nonmembers_are_protected(self):
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.first.player.pvp_organization = "anbu"
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.assertIsNone(self.first.pvp_target)

    def test_rivals_fight_allies_cannot(self):
        self.first.player.pvp_organization = "anbu"
        self.second.player.pvp_organization = "anbu"
        self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.second.player.pvp_organization = "root"
        self.assertTrue(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.assertIs(self.first.pvp_target, self.second)

    def test_duels_are_available_to_nonmembers_and_allies(self):
        self.assertFalse(org.allowed_sessions(self.first, self.second))
        fight = duel.start_duel(self.first, self.second)
        self.assertFalse(org.allowed_sessions(self.first, self.second))
        fight.accepted = True
        self.assertTrue(org.allowed_sessions(self.first, self.second))
        self.assertTrue(combat.engage_damage_attack(self.first, self.second.player, self.second))
        self.first.pvp_target = self.second.pvp_target = None
        self.first.player.pvp_organization = "anbu"
        self.second.player.pvp_organization = "anbu"
        self.assertTrue(org.allowed_sessions(self.first, self.second))

    def test_duel_command_does_not_require_membership(self):
        commands.cmd_duel(self.first, ["Second"])
        self.assertIs(self.first.duel, self.second.duel)
        self.assertFalse(self.first.duel.accepted)
        with patch("duel.begin_duel"):
            commands.cmd_duel(self.second, ["First"])
        self.assertTrue(self.first.duel.accepted)

    def test_safe_room_blocks_pvp_even_during_duel(self):
        fight = duel.start_duel(self.first, self.second)
        fight.accepted = True
        with patch.object(combat.world.WORLD, "get", return_value=NS(safe=True)):
            self.assertFalse(combat.engage_damage_attack(self.first, self.second.player, self.second))

    def test_direct_join_blocked_leader_appointee_only_can_invite(self):
        org.command(self.first, ["join", "anbu"])
        self.assertFalse(org.membership(self.first.player))
        org.command(self.first, ["appoint", "anbu", "First"])  # not immortal
        self.assertFalse(leadership._leader("anbu"))
        self.appoint()
        self.assertEqual(leadership._leader("anbu"), "First")
        self.assertEqual(org.membership(self.first.player), "anbu")
        org.command(self.first, ["invite", "Second"])
        self.assertEqual(self.second.player.pvp_organization_invite, "anbu")
        self.assertFalse(org.membership(self.second.player))
        self.assertEqual(self.second.player.pvp_organization_invited_by, "First")
        org.command(self.second, ["accept"])
        self.assertEqual(org.membership(self.second.player), "anbu")
        self.assertFalse(self.second.player.pvp_organization_invite)
        self.assertFalse(org.allowed(self.first.player, self.second.player))
        self.save.assert_called()

    def test_village_checks_and_decline(self):
        self.appoint()
        self.second.player.village = "water"
        org.command(self.first, ["invite", "Second"])
        self.assertFalse(self.second.player.pvp_organization_invite)
        self.second.player.village = "leaf"
        org.command(self.first, ["invite", "Second"])
        org.command(self.second, ["decline"])
        self.assertFalse(self.second.player.pvp_organization_invite)
        self.assertFalse(org.membership(self.second.player))

    def test_expired_or_replaced_leader_invites_are_invalid(self):
        self.appoint()
        org.command(self.first, ["invite", "Second"])
        self.second.player.pvp_organization_invite_expires_at = 1.0
        org.command(self.second, ["accept"])
        self.assertFalse(org.membership(self.second.player))
        org.command(self.first, ["invite", "Second"])
        self.appoint(name="Second")
        self.assertEqual(leadership._leader("anbu"), "Second")
        self.second.player.pvp_organization = ""
        self.second.player.pvp_organization_invite = "anbu"
        self.second.player.pvp_organization_invited_by = "First"
        self.second.player.pvp_organization_invite_expires_at = org.time.time() + 500
        org.command(self.second, ["accept"])
        self.assertFalse(org.membership(self.second.player))

    def test_leader_cannot_leave_but_member_can_after_cooldown(self):
        self.appoint()
        org.command(self.first, ["leave"])
        self.assertEqual(org.membership(self.first.player), "anbu")
        org.command(self.first, ["invite", "Second"])
        org.command(self.second, ["accept"])
        org.command(self.second, ["leave"])
        self.assertEqual(org.membership(self.second.player), "anbu")
        self.second.player.pvp_organization_changed_at -= 86401
        org.command(self.second, ["leave"])
        self.assertFalse(org.membership(self.second.player))

    def test_hideout_assignment_does_not_create_or_modify_world_rooms(self):
        self.appoint()
        world_room_count = len(combat.world.WORLD.rooms)
        org.command(self.first, ["sethideout", "anbu", "133750"])
        self.assertEqual(leadership._hideout("anbu"), 0)
        self.first.account.staff_level = "implementor"
        org.command(self.first, ["sethideout", "anbu", "133750"])
        self.assertEqual(leadership._hideout("anbu"), 133750)
        org.command(self.first, ["sethideout", "root", "133750"])
        self.assertEqual(leadership._hideout("root"), 0)
        self.assertEqual(len(combat.world.WORLD.rooms), world_room_count)
        org.command(self.first, ["sethideout", "anbu", "none"])
        self.assertEqual(leadership._hideout("anbu"), 0)

    def test_membership_and_pending_invites_survive_player_roundtrip(self):
        self.appoint()
        org.command(self.first, ["invite", "Second"])
        restored = Player.from_dict(self.second.player.to_dict())
        self.assertEqual(restored.pvp_organization_invite, "anbu")
        self.assertEqual(restored.pvp_organization_invited_by, "First")
        self.assertEqual(Player("New", "New").pvp_organization, "")


if __name__ == "__main__":
    unittest.main()
