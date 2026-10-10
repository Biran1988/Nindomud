"""An incomplete update cannot take an online server down during reboot."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands


class RebootPreflightTests(unittest.TestCase):
    def test_failed_import_keeps_server_and_players_online(self):
        session = NS(account=NS(staff_level="implementor"), player=NS(), send=Mock())
        with patch.object(commands, "_reboot_preflight", return_value="ModuleNotFoundError: jutsu_colors"), \
             patch.object(commands, "_reboot_process") as restart, \
             patch("session.ACTIVE_SESSIONS", [session]), \
             patch.object(commands.storage, "save_player") as save:
            commands.cmd_reboot(session, [])
        restart.assert_not_called()
        save.assert_not_called()
        self.assertIn("still online", session.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
