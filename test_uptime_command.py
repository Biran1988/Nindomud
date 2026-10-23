"""Uptime display from live server start, reset on restart, all-player access."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import clone_control
import server_uptime
from models import Player


class UptimeCommandTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("UptimeTester", "UptimeTester",
                             village="leaf", clan="nara", primary_class="taijutsu")
        self.session = NS(player=self.player, send=Mock())
        self.previous = server_uptime._started_at
        self.addCleanup(lambda: setattr(server_uptime, "_started_at", self.previous))

    def test_timer_starts_at_zero_and_formats_large_values(self):
        server_uptime._started_at = None
        self.assertEqual(server_uptime.format_uptime(), "0d 00h 00m 00s")
        with patch.object(server_uptime.time, "monotonic", side_effect=[
                100.0, 100.0, 100.0 + 2 * 86400 + 4 * 3600 + 16 * 60 + 7]):
            server_uptime.start()
            self.assertEqual(server_uptime.format_uptime(), "0d 00h 00m 00s")
            self.assertEqual(server_uptime.format_uptime(), "2d 04h 16m 07s")

    def test_reset_on_new_server_start(self):
        with patch.object(server_uptime.time, "monotonic", side_effect=[
                100.0, 150.0, 200.0, 201.0]):
            server_uptime.start()
            self.assertEqual(server_uptime.format_uptime(), "0d 00h 00m 50s")
            server_uptime.start()
            self.assertEqual(server_uptime.format_uptime(), "0d 00h 00m 01s")

    def test_command_and_help_are_registered(self):
        self.assertIs(commands.COMMANDS["uptime"], commands.cmd_uptime)
        with patch.object(server_uptime, "format_uptime", return_value="1d 02h 03m 04s"):
            commands.dispatch_line(self.session, "uptime")
        self.assertEqual(self.session.send.call_args.args[0],
                         "&CNindo_mud uptime:&x 1d 02h 03m 04s")

    def test_readable_during_sleep_and_genjutsu_freeze(self):
        with patch.object(server_uptime, "format_uptime", return_value="0d 00h 05m 00s"):
            self.player.position = "sleeping"
            commands.dispatch_line(self.session, "uptime")
            self.assertIn("05m", self.session.send.call_args.args[0])
            self.session.send.reset_mock()
            self.player.position = "standing"
            self.player.tsukuyomi_frozen = True
            commands.dispatch_line(self.session, "uptime")
            self.assertIn("05m", self.session.send.call_args.args[0])
            self.session.send.reset_mock()
            self.player.tsukuyomi_frozen = False
            self.player.active_status_effects["asleep"] = {"remaining": 1}
            commands.dispatch_line(self.session, "uptime")
            self.assertIn("05m", self.session.send.call_args.args[0])

    def test_clone_uses_same_server_timer(self):
        self.assertIn("uptime", clone_control.SENSE_VERBS)


if __name__ == "__main__":
    unittest.main()
