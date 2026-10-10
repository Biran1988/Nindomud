"""A Tsukuyomi target cannot fight or complete a queued cast, even as staff."""

import unittest
import tempfile
from unittest.mock import patch

import combat
import mangekyo
import world
import storage
from models import Account, Player
from session import Session, State


class TsukuyomiFreezeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        sessions = []
        rooms = {1: world.Room(1, "Test room", "A quiet room."),
                 2: world.Room(2, "Other room", "Another room.")}
        for target, value in (("session.ACTIVE_SESSIONS", sessions),
                              ("world.WORLD.rooms", rooms),
                              ("mangekyo._NEXT_TSUKUYOMI_ROOM_VNUM", None),
                              ("storage.DATA_DIR", directory.name),
                              ("storage.ACCOUNTS_DIR", directory.name + "/accounts"),
                              ("storage.PLAYERS_DIR", directory.name + "/players")):
            item = patch(target, value)
            item.start()
            self.addCleanup(item.stop)
        self.caster, self.caster_out = self.make_session("Caster", "player")
        self.target, self.target_out = self.make_session("Immortal", "implementor")

    @staticmethod
    def make_session(name, staff_level):
        output = []
        session = Session(output.append, lambda: None)
        session.player = Player(name, name, room_vnum=1, chakra=100, maximum_chakra=100)
        session.player.village = "leaf"
        session.account = Account(name, "", "", staff_level=staff_level)
        session.state = State.PLAYING
        session.color_enabled = False
        output.clear()
        return session, output

    def test_immortal_target_cannot_attack_cast_or_escape_while_frozen(self):
        self.caster.pvp_target = self.target
        self.target.pvp_target = self.caster
        self.target.pending_cast = object()
        self.target.pending_action = {"resolve_at": 0, "resolve_fn": lambda: None}
        self.target.chakra_charge = {"total": 10}
        mangekyo.open_tsukuyomi(self.caster, self.target, world)
        self.assertIsNone(self.target.pvp_target)
        self.assertIsNone(self.caster.pvp_target)
        self.assertIsNone(self.target.pending_cast)
        self.assertIsNone(self.target.pending_action)
        self.assertIsNone(self.target.chakra_charge)
        self.assertTrue(self.target.player.tsukuyomi_frozen)

        room = self.target.player.room_vnum
        for command in ("attack Caster", "perform fireball jutsu Caster", "goto 2", "north"):
            with self.subTest(command=command):
                self.target.handle_line(command)
                self.assertIn("frozen inside Tsukuyomi", "".join(self.target_out))
                self.assertIsNone(self.target.pvp_target)
                self.assertEqual(self.target.player.room_vnum, room)
                self.assertEqual(self.target.player.chakra, 100)
                self.target_out.clear()
        combat.resolve_pvp_pulse(self.target)
        self.assertIsNone(self.target.pvp_target)

        mangekyo.end_tsukuyomi(self.caster, self.target, world)
        self.assertFalse(self.target.player.tsukuyomi_frozen)
        self.target.handle_line("attack Caster")
        self.assertIs(self.target.pvp_target, self.caster)

    def test_departure_releases_both_players_and_saves_unfrozen_state(self):
        mangekyo.open_tsukuyomi(self.caster, self.target, world)
        room = self.caster.player.room_vnum
        self.target.request_close()
        self.assertFalse(self.target.player.tsukuyomi_frozen)
        self.assertIsNone(self.caster.player.tsukuyomi_active_target_name)
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertNotIn(room, world.WORLD.rooms)
        self.assertFalse(storage.load_player("Immortal").tsukuyomi_frozen)

    def test_login_clears_stale_freeze_after_reboot(self):
        stale = Player("Immortal", "Immortal", room_vnum=999999)
        stale.village = "leaf"
        stale.tsukuyomi_frozen = True
        stale.tsukuyomi_return_room_vnum = 1
        self.target.player = None
        self.target.state = State.CLOSED
        new_session, _ = self.make_session("Reconnected", "implementor")
        new_session._enter_world(stale)
        self.assertFalse(stale.tsukuyomi_frozen)
        self.assertEqual(stale.room_vnum, 1)


if __name__ == "__main__":
    unittest.main()
