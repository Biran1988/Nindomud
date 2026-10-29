"""Regression tests for reconnect grace, combat immunity, and expiry."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import commands
import groups
import session
import storage
from models import Player


class LinkdeadGraceTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(session, "ACTIVE_SESSIONS", [])
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(storage, "save_player")
        p.start()
        self.addCleanup(p.stop)

        self.closed = Mock()
        self.session = session.Session(Mock(), self.closed)
        self.player = Player("LinkdeadTester", "LinkdeadTester")
        self.player.village = "leaf"
        self.player.clan = "nara"
        self.player.room_vnum = 1
        self.session.player = self.player
        self.session.state = session.State.PLAYING

    def test_protected_grace_lasts_900_seconds(self):
        self.session.begin_disconnect_grace(now=100)
        self.assertEqual(self.session.state, session.State.LINKDEAD)
        self.assertEqual(self.session.linkdead_until, 1000)
        self.assertIn(self.session, session.ACTIVE_SESSIONS)
        self.assertEqual(session.expire_linkdead_sessions(now=999.99), 0)
        self.assertEqual(self.session.state, session.State.LINKDEAD)
        self.assertEqual(session.expire_linkdead_sessions(now=1000), 1)
        self.assertEqual(self.session.state, session.State.CLOSED)
        self.assertNotIn(self.session, session.ACTIVE_SESSIONS)
        self.closed.assert_called_once()

    def test_disconnect_breaks_pvp_and_immunizes_player(self):
        enemy = session.Session(Mock(), Mock())
        enemy.player = Player("Opponent", "Opponent")
        enemy.state = session.State.PLAYING
        enemy.pvp_target = self.session
        self.session.pvp_target = enemy
        self.session.combat_target = object()
        hp = self.player.health
        self.session.begin_disconnect_grace(now=100)
        self.assertIsNone(enemy.pvp_target)
        self.assertIsNone(self.session.pvp_target)
        self.assertIsNone(self.session.combat_target)
        combat.start_pvp_attack(enemy, self.session)
        self.assertIsNone(enemy.pvp_target)
        combat._player_attack_target_once(enemy, enemy.player, self.session, self.player)
        self.assertEqual(self.player.health, hp)
        combat.use_jutsu_on_player(enemy, "fireball jutsu", self.session)
        self.assertEqual(self.player.health, hp)

    def test_reconnect_reclaims_same_live_character_and_group(self):
        old = self.session
        follower = session.Session(Mock(), Mock())
        follower.player = Player("Follower", "Follower")
        follower.state = session.State.PLAYING
        grp = groups.Group(old)
        grp.members.append(follower)
        old.group = grp
        follower.group = grp
        self.player.stamina = 13
        old.begin_disconnect_grace(now=100)
        old.linkdead_until = time.time() + 600

        login = session.Session(Mock(), Mock())
        login.account = SimpleNamespace(staff_level="player")
        disk_player = Player("LinkdeadTester", "LinkdeadTester")
        disk_player.village = "leaf"
        disk_player.clan = "nara"
        disk_player.room_vnum = 1
        disk_player.stamina = 99
        with (
            patch.object(session.world.WORLD, "get", return_value=SimpleNamespace(
                name="Test Room", description="Room.", exits={}, flags=[])),
            patch.object(session.commands, "cmd_look"),
            patch.object(session.leveling, "sync_universal_skills", return_value=[]),
            patch("element_choice.begin"),
        ):
            login._enter_world(disk_player)
        self.assertIs(login.player, self.player)
        self.assertEqual(login.player.stamina, 13)
        self.assertEqual(login.state, session.State.PLAYING)
        self.assertIs(grp.leader, login)
        self.assertIn(login, grp.members)
        self.assertNotIn(old, grp.members)
        self.assertNotIn(old, session.ACTIVE_SESSIONS)

    def test_not_online_or_attackable_but_listed_as_linkdead(self):
        observer = session.Session(Mock(), Mock())
        observer.player = Player("Observer", "Observer")
        observer.player.village = "leaf"
        observer.player.clan = "nara"
        observer.state = session.State.PLAYING
        self.session.begin_disconnect_grace(now=100)
        self.assertNotIn(self.session, observer.active_sessions())
        commands.cmd_who(observer, [])
        self.assertIn("LINKDEAD", observer.send_raw.call_args.args[0])

    def test_offline_commands_are_disabled(self):
        self.session.begin_disconnect_grace(now=100)
        with patch.object(commands, "cmd_move") as move:
            commands.dispatch_line(self.session, "north")
        move.assert_not_called()


if __name__ == "__main__":
    unittest.main()
