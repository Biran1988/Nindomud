"""Real Izanami cast, 15-second loop, damage and caster-feedback regressions."""
import tempfile
import unittest
from unittest.mock import patch

import combat
import commands
import izanami_loops
import mangekyo_discovery
import storage
import world
from models import Account, Player
from session import Session, State


class IzanamiLoopTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name, value in (
            ("session.ACTIVE_SESSIONS", []),
            ("world.WORLD.rooms", {1: world.Room(1, "Arena", "A combat arena.")}),
            ("storage.DATA_DIR", temp.name),
            ("storage.ACCOUNTS_DIR", temp.name + "/accounts"),
            ("storage.PLAYERS_DIR", temp.name + "/players"),
        ):
            p = patch(name, value)
            p.start()
            self.addCleanup(p.stop)
        self.caster, self.caster_out = self.make_session("Caster")
        self.victim, self.victim_out = self.make_session("Victim")
        with (patch("izanami_loops.time.time", return_value=1000.0),
              patch("random.randint", return_value=13),
              patch.object(mangekyo_discovery, "record_use")):
            combat.resolve_izanami_cast(self.caster, self.victim, grow_handsigns=False)
        self.caster_out.clear()
        self.victim_out.clear()

    @staticmethod
    def make_session(name):
        output = []
        s = Session(output.append, lambda: None)
        s.account = Account(name, "", "")
        s.player = Player(
            name, name, room_vnum=1, health=1000, maximum_health=1000,
            chakra=1000, maximum_chakra=1000,
            stamina=1000, maximum_stamina=1000
        )
        s.state = State.PLAYING
        s.color_enabled = False
        output.clear()
        return s, output

    def test_wrong_guess_damages_and_privately_notifies_caster(self):
        with (patch("izanami_loops.time.time", return_value=1001.0),
              patch("izanami_loops.random.randint", return_value=10)):
            commands.cmd_guess(self.victim, ["5"])
        self.assertEqual(self.victim.player.health, 900)
        self.assertTrue(self.victim.player.izanami_trapped)
        self.assertIn("100 Health damage", "".join(self.victim_out))
        self.assertIn("Victim guessed 5 incorrectly", "".join(self.caster_out))
        self.assertIn("100 Health damage", "".join(self.caster_out))
        self.assertTrue(self.victim.player.izanami_guessed_this_loop)

    def test_only_one_guess_every_fifteen_seconds_then_correct_release(self):
        with (patch("izanami_loops.random.randint", return_value=8),
              patch("izanami_loops.time.time", return_value=1001.0)):
            self.victim.handle_line("guess 2")
        self.assertEqual(self.victim.player.health, 920)
        with patch("izanami_loops.time.time", return_value=1014.9):
            self.victim.handle_line("guess 13")
        self.assertEqual(self.victim.player.health, 920)
        self.assertTrue(self.victim.player.izanami_trapped)
        self.assertIn("already guessed", "".join(self.victim_out))
        with patch("izanami_loops.time.time", return_value=1015.0):
            self.victim.handle_line("guess 13")
        self.assertFalse(self.victim.player.izanami_trapped)
        self.assertIsNone(self.victim.player.izanami_target_number)
        self.assertEqual(self.victim.player.izanami_loop_ends_at, 0)
        self.assertIn("guessed correctly and escaped", "".join(self.caster_out))
        self.assertEqual(self.victim.player.room_vnum, 1)

    def test_no_auto_expiry_and_loop_ticker_notifies_only_once(self):
        self.victim.player.izanami_guessed_this_loop = True
        with patch("izanami_loops.time.time", return_value=1015.0):
            izanami_loops.process()
            izanami_loops.process()
        self.assertFalse(self.victim.player.izanami_guessed_this_loop)
        self.assertEqual("".join(self.victim_out).count("may guess again"), 1)
        with patch("izanami_loops.time.time", return_value=10000.0):
            izanami_loops.process()
        self.assertTrue(self.victim.player.izanami_trapped)
        self.assertEqual(self.victim.player.izanami_target_number, 13)

    def test_movement_attack_jutsu_staff_escape_blocked_but_look_allowed(self):
        old_room = self.victim.player.room_vnum
        for line in ("north", "attack Caster", "perform fireball jutsu Caster",
                     "goto 2", "recall", "run", "follow Caster"):
            with self.subTest(command=line):
                self.victim.handle_line(line)
                self.assertEqual(self.victim.player.room_vnum, old_room)
                self.assertIn("trapped in Izanami", "".join(self.victim_out))
                self.victim_out.clear()
        commands.cmd_move(self.victim, "north")
        self.assertIn("trapped in Izanami", "".join(self.victim_out))
        self.victim_out.clear()
        self.victim.handle_line("look")
        self.assertNotIn("trapped in Izanami", "".join(self.victim_out))

    def test_invalid_guess_never_consumes_slot_and_1hp_remains_nonlethal(self):
        with patch("izanami_loops.time.time", return_value=1001.0):
            for invalid in (["nope"], ["0"], ["26"], [], ["13", "2"]):
                commands.cmd_guess(self.victim, invalid)
        self.assertFalse(self.victim.player.izanami_guessed_this_loop)
        self.victim.player.health = 2
        with (patch("izanami_loops.random.randint", return_value=12),
              patch("izanami_loops.time.time", return_value=1001.0)):
            commands.cmd_guess(self.victim, ["1"])
        self.assertEqual(self.victim.player.health, 1)
        self.assertTrue(self.victim.player.izanami_trapped)

    def test_saving_and_reconnecting_does_not_reset_guess_cooldown(self):
        with (patch("izanami_loops.random.randint", return_value=10),
              patch("izanami_loops.time.time", return_value=1001.0)):
            commands.cmd_guess(self.victim, ["1"])
        restored = Player.from_dict(self.victim.player.to_dict())
        self.victim.player = restored
        self.assertEqual(restored.izanami_loop_ends_at, 1015.0)
        self.assertTrue(restored.izanami_guessed_this_loop)
        with patch("izanami_loops.time.time", return_value=1002.0):
            commands.cmd_guess(self.victim, ["13"])
        self.assertTrue(restored.izanami_trapped)
        with patch("izanami_loops.time.time", return_value=1015.0):
            commands.cmd_guess(self.victim, ["13"])
        self.assertFalse(restored.izanami_trapped)

    def test_only_caster_is_notified_not_third_party(self):
        observer, out = self.make_session("Observer")
        with (patch("izanami_loops.time.time", return_value=1001.0),
              patch("izanami_loops.random.randint", return_value=10)):
            commands.cmd_guess(self.victim, ["2"])
        self.assertEqual(out, [])
        self.assertIn("guessed 2 incorrectly", "".join(self.caster_out))
        with patch("izanami_loops.time.time", return_value=1015.0):
            commands.cmd_guess(self.victim, ["13"])
        self.assertEqual(out, [])
        self.assertIn("guessed correctly", "".join(self.caster_out))

    def test_cannot_recast_to_reset_number_and_cycle(self):
        with (patch("izanami_loops.time.time", return_value=1002.0),
              patch("random.randint", return_value=1)):
            combat.resolve_izanami_cast(self.caster, self.victim, grow_handsigns=False)
        self.assertEqual(self.victim.player.izanami_target_number, 13)
        self.assertEqual(self.victim.player.izanami_loop_ends_at, 1015.0)
        self.assertIn("already trapped", "".join(self.caster_out))


if __name__ == "__main__":
    unittest.main()
