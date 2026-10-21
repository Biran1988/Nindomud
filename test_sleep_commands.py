"""Sleeping prevents room awareness and physical commands until waking."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands


class SleepingCommandTests(unittest.TestCase):
    def setUp(self):
        self.player = NS(position="sleeping", downed_by=None, frozen_until=0,
                         rampage_until=0, active_status_effects={},
                         tsukuyomi_frozen=False)
        self.session = NS(player=self.player, send=Mock())

    def test_look_and_alias_are_blocked(self):
        with patch.object(commands, "cmd_look") as look:
            commands.dispatch(self.session, "look", [])
            commands.dispatch_line(self.session, "l")
            look.assert_not_called()
        self.assertIn("You are sleeping", self.session.send.call_args.args[0])

    def test_movement_is_blocked_without_auto_waking(self):
        with patch.object(commands, "cmd_move") as move:
            commands.dispatch_line(self.session, "north")
            move.assert_not_called()
        self.assertEqual(self.player.position, "sleeping")

    def test_wake_and_stand_work(self):
        commands.dispatch_line(self.session, "wake")
        self.assertEqual(self.player.position, "standing")

    def test_normal_look_after_waking(self):
        self.player.position = "standing"
        with patch.dict(commands.COMMANDS, {"look": Mock()}) as updated:
            commands.dispatch(self.session, "look", [])
            commands.COMMANDS["look"].assert_called_once_with(self.session, [])

    def test_bare_jutsu_is_blocked(self):
        with patch.object(commands.data_jutsu, "match_prefix", side_effect=AssertionError("jutsu parsed")):
            commands.dispatch_line(self.session, "dynamic entry target")
        self.assertEqual(self.player.position, "sleeping")

    def test_help_is_still_available(self):
        with patch.dict(commands.COMMANDS, {"help": Mock()}):
            commands.dispatch(self.session, "help", [])
            commands.COMMANDS["help"].assert_called_once_with(self.session, [])


if __name__ == "__main__":
    unittest.main()
