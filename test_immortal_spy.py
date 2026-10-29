"""Administrative observation, safeguards, and quiet linkdead regression tests."""
import unittest
from unittest.mock import patch

import immortal_spy
from models import Account, Player
from session import ACTIVE_SESSIONS, Session, State


class SpyTests(unittest.TestCase):
    def setUp(self):
        self.admin_output = []
        self.player_output = []
        self.admin = Session(self.admin_output.append, lambda: None)
        self.target = Session(self.player_output.append, lambda: None)
        self.admin.state = self.target.state = State.PLAYING
        self.admin.account = Account("Admin", "", "")
        self.admin.account.staff_level = "implementor"
        self.admin.player = Player("Admin", "Admin")
        self.target.account = Account("Ninja", "", "")
        self.target.player = Player("Ninja", "Ninja")
        self.admin_output.clear()
        self.player_output.clear()
        self.audit = patch("olc._log")
        self.mock_log = self.audit.start()
        self.addCleanup(self.audit.stop)
        self.addCleanup(lambda: ACTIVE_SESSIONS.remove(self.target)
                        if self.target in ACTIVE_SESSIONS else None)
        self.addCleanup(lambda: ACTIVE_SESSIONS.remove(self.admin)
                        if self.admin in ACTIVE_SESSIONS else None)

    def test_only_administrators_can_observe_regular_players(self):
        self.admin.account.staff_level = "builder"
        immortal_spy.command(self.admin, ["Ninja"])
        self.assertIsNone(self.admin.spy_target)
        self.admin.account.staff_level = "administrator"
        immortal_spy.command(self.admin, ["Ninja"])
        self.assertIs(self.admin.spy_target, self.target)
        self.assertEqual(self.mock_log.call_count, 1)
        immortal_spy.command(self.admin, ["off"])
        self.assertIsNone(self.admin.spy_target)

    def test_input_output_prompt_forwarding_and_password_redaction(self):
        immortal_spy.command(self.admin, ["Ninja"])
        self.admin_output.clear()
        immortal_spy.forward_input(self.target, "say hello")
        immortal_spy.forward_input(self.target, "password my-private-credential")
        self.target.send("A bandit approaches.")
        self.target.send_prompt()
        joined = "".join(self.admin_output)
        self.assertIn("say hello", joined)
        self.assertIn("[REDACTED: sensitive command]", joined)
        self.assertNotIn("my-private-credential", joined)
        self.assertIn("A bandit approaches.", joined)
        self.assertIn("PROMPT", joined)

    def test_disconnected_target_stops_watch_without_global_notice(self):
        immortal_spy.command(self.admin, ["Ninja"])
        with patch("storage.save_player"):
            self.admin_output.clear()
            self.target.begin_disconnect_grace()
        self.assertEqual(self.target.state, State.LINKDEAD)
        self.assertIsNone(self.admin.spy_target)
        joined = "".join(self.admin_output)
        self.assertIn("observation stopped", joined.lower())
        self.assertNotIn("[LINKDEAD]", joined)


if __name__ == "__main__":
    unittest.main()
