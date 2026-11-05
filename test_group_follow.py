"""Group follow is opt-in and respects normal walking restrictions."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import combat
import commands
import groups
import general_skills
import reaper_seal
import session as session_module
from models import Player
from world import Room


class GroupFollowTests(unittest.TestCase):
    def setUp(self):
        self.rooms = {
            75001: Room(75001, "Start", "Start"),
            75002: Room(75002, "North", "North"),
            75003: Room(75003, "East", "East"),
        }
        self.rooms[75001].exits.update({"north": 75002, "east": 75003})
        self.rooms[75002].exits["south"] = 75001
        self.rooms[75003].exits["west"] = 75001
        self.clients = []
        self.leader = self.make("Leader")
        self.follower = self.make("Follower")
        self.second = self.make("Second")
        self.group = groups.Group(self.leader)
        self.group.members.extend([self.follower, self.second])
        for client in self.group.members:
            client.group = self.group
        for obj, name, value in (
            (commands.WORLD, "get", self.rooms.get),
            (commands.combat, "mobs_in_room", lambda vnum: []),
            (commands.olc, "_require_assigned_vnum", lambda *a: True),
            (commands, "cmd_look", lambda *a: None),
            (commands, "_fire_enter_triggers", lambda *a: None),
            (general_skills, "before_move", lambda *a: None),
            (general_skills, "broadcast_movement", lambda *a: None),
            (commands.random, "randint", lambda *a: 1),
            (reaper_seal, "blocks_command", lambda *a: False),
        ):
            p = patch.object(obj, name, value)
            p.start()
            self.addCleanup(p.stop)

    def make(self, name):
        client = session_module.Session(Mock(), Mock(),
                                        connection_ip=f"198.51.100.{len(self.clients) + 20}")
        client.account = SimpleNamespace(name=name, staff_level="player")
        client.player = Player(name=name, account_name=name, village="leaf",
                               room_vnum=75001, stamina=10)
        client.state = session_module.State.PLAYING
        self.clients.append(client)
        return client

    def test_follow_is_opt_in_and_group_leader_is_followable(self):
        commands.cmd_move(self.leader, "north")
        self.assertEqual(self.follower.player.room_vnum, 75001)
        self.assertEqual(self.second.player.room_vnum, 75001)
        self.leader.player.room_vnum = 75001
        commands.cmd_follow(self.follower, ["SomeoneElse"])
        self.assertFalse(self.follower.follow_group_leader)
        commands.cmd_follow(self.follower, ["leader"])
        self.assertTrue(self.follower.follow_group_leader)
        self.assertFalse(self.second.follow_group_leader)
        commands.cmd_group(self.follower, [])
        self.assertIn("(Following)", self.follower.send_raw.call_args.args[0])

    def test_followers_walk_same_exit_at_own_stamina_cost(self):
        commands.cmd_follow(self.follower, ["Leader"])
        commands.cmd_follow(self.second, ["Leader"])
        commands.dispatch(self.leader, "north", [])
        self.assertEqual([c.player.room_vnum for c in self.group.members],
                         [75002, 75002, 75002])
        self.assertEqual([c.player.stamina for c in self.group.members],
                         [9, 9, 9])
        commands.cmd_follow(self.second, ["off"])
        self.assertFalse(self.second.follow_group_leader)
        commands.dispatch(self.leader, "south", [])
        self.assertEqual(self.leader.player.room_vnum, 75001)
        self.assertEqual(self.follower.player.room_vnum, 75001)
        self.assertEqual(self.second.player.room_vnum, 75002)

    def test_exhaustion_does_not_teleport_or_break_follow_opt_in(self):
        commands.cmd_follow(self.follower, ["leader"])
        self.follower.player.stamina = 0
        commands.cmd_move(self.leader, "north")
        self.assertEqual(self.leader.player.room_vnum, 75002)
        self.assertEqual(self.follower.player.room_vnum, 75001)
        self.assertTrue(self.follower.follow_group_leader)
        self.assertTrue(any("exhausted" in call.args[0]
                            for call in self.follower.send_raw.call_args_list))
        self.follower.player.stamina = 10
        commands.cmd_move(self.follower, "north")
        commands.cmd_move(self.leader, "south")
        self.assertEqual(self.follower.player.room_vnum, 75001)

    def test_combat_and_linkdead_members_do_not_follow(self):
        commands.cmd_follow(self.follower, ["leader"])
        commands.cmd_follow(self.second, ["leader"])
        self.follower.combat_target = object()
        self.second.state = session_module.State.LINKDEAD
        commands.cmd_move(self.leader, "north")
        self.assertEqual(self.follower.player.room_vnum, 75001)
        self.assertEqual(self.second.player.room_vnum, 75001)
        self.assertTrue(self.follower.follow_group_leader)

    def test_leadership_change_preserves_opt_in_for_remaining_members(self):
        commands.cmd_follow(self.follower, ["leader"])
        commands.cmd_follow(self.second, ["leader"])
        commands.cmd_group(self.leader, ["leave"])
        self.assertIs(self.group.leader, self.follower)
        self.assertFalse(self.follower.follow_group_leader)
        self.assertTrue(self.second.follow_group_leader)
        self.assertFalse(self.leader.follow_group_leader)
        commands.cmd_move(self.follower, "north")
        self.assertEqual(self.second.player.room_vnum, 75002)

    def test_unfollow_and_disband_clear_follow_flags(self):
        commands.cmd_group(self.follower, ["follow", "on"])
        self.assertTrue(self.follower.follow_group_leader)
        commands.dispatch(self.follower, "unfollow", [])
        self.assertFalse(self.follower.follow_group_leader)
        commands.cmd_follow(self.follower, ["leader"])
        commands.cmd_group(self.leader, ["disband"])
        self.assertIsNone(self.follower.group)
        self.assertFalse(self.follower.follow_group_leader)

    def test_script_teleport_does_not_pull_follower(self):
        commands.cmd_follow(self.follower, ["leader"])
        with patch.object(commands, "_fire_enter_triggers",
                          side_effect=lambda s: setattr(s.player, "room_vnum", 75003)):
            commands.cmd_move(self.leader, "north")
        self.assertEqual(self.leader.player.room_vnum, 75003)
        self.assertEqual(self.follower.player.room_vnum, 75001)

    def test_follow_before_group_all_and_cooperative_mob_combat(self):
        leader = self.make("NewLeader")
        follower = self.make("NewFollower")
        another = self.make("NewAnother")
        commands.cmd_follow(follower, ["NewLeader"])
        commands.cmd_follow(another, ["NewLeader"])
        self.assertIs(follower.follow_target, leader)
        self.assertIsNone(follower.group)
        commands.cmd_move(leader, "north")
        self.assertEqual(follower.player.room_vnum, 75002)
        self.assertEqual(another.player.room_vnum, 75002)
        commands.cmd_group(leader, ["all"])
        self.assertIsNotNone(leader.group)
        self.assertEqual(len(leader.group.members), 3)
        self.assertIs(follower.group, leader.group)
        self.assertTrue(follower.follow_group_leader)
        mob = SimpleNamespace(name="a wolf", room_vnum=75002, health=100,
                              template_vnum=9999, chunin_exam_owner="")
        with patch.object(combat, "is_immortal_mob", return_value=False):
            combat.start_attack(leader, mob)
        self.assertIs(follower.combat_target, mob)
        self.assertIs(another.combat_target, mob)

    def test_existing_opponent_or_other_room_blocks_group_assist(self):
        leader = self.make("PartyLead")
        follower = self.make("PartyMember")
        commands.cmd_follow(follower, ["PartyLead"])
        commands.cmd_group(leader, ["all"])
        other = object()
        follower.combat_target = other
        mob = SimpleNamespace(name="boar", room_vnum=75001, health=100,
                              template_vnum=9998, chunin_exam_owner="")
        with patch.object(combat, "is_immortal_mob", return_value=False):
            combat.start_attack(leader, mob)
        self.assertIs(follower.combat_target, other)
        follower.combat_target = None
        follower.player.room_vnum = 75002
        with patch.object(combat, "is_immortal_mob", return_value=False):
            combat.start_attack(leader, mob)
        self.assertIsNone(follower.combat_target)

    def test_disconnected_or_distant_leader_cannot_be_followed(self):
        self.leader.player.room_vnum = 75002
        commands.cmd_follow(self.follower, ["leader"])
        self.assertFalse(self.follower.follow_group_leader)
        self.leader.player.room_vnum = 75001
        self.leader.state = session_module.State.LINKDEAD
        commands.cmd_follow(self.follower, ["leader"])
        self.assertFalse(self.follower.follow_group_leader)


if __name__ == "__main__":
    unittest.main()
