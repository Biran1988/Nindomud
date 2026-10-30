"""Mangekyo betrayal anti-abuse checks with persisted account suspensions."""
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import mangekyo_ip_guard as guard
import session as session_module
import storage
from models import Account, Player


class MangekyoIPGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in (
            ("ACCOUNTS_DIR", self.tmp.name + "/accounts"),
            ("PLAYERS_DIR", self.tmp.name + "/players"),
            ("DATA_DIR", self.tmp.name),
        ):
            p = patch.object(storage, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.attacker = Player("Caster", "Caster")
        self.victim = Player("Victim", "Victim")
        self.victim.downed_by = self.attacker.name
        self.account = Account("Caster", "salt", "hash")
        storage.save_account(self.account)
        self.caster = NS(player=self.attacker, account=self.account,
                         connection_ip="192.0.2.10", send=Mock(),
                         request_close=Mock())
        self.target = NS(player=self.victim, account=Account("Victim", "salt", "hash"),
                         connection_ip="192.0.2.11", send=Mock(), send_prompt=Mock())
        p = patch.object(session_module, "ACTIVE_SESSIONS", [self.caster, self.target])
        p.start()
        self.addCleanup(p.stop)

    def test_normalization_and_absent_addresses(self):
        self.target.connection_ip = "::ffff:192.0.2.10"
        self.assertTrue(guard.ip_comparison(self.caster, self.target))
        self.target.connection_ip = "2001:db8::100"
        self.assertFalse(guard.ip_comparison(self.caster, self.target))
        self.target.connection_ip = "garbage"
        self.assertIsNone(guard.ip_comparison(self.caster, self.target))

    def test_same_ip_blocks_eye_unlock_and_suspends_only_attacker(self):
        self.target.connection_ip = "192.0.2.10"
        with patch("mangekyo_ip_guard.time.time", return_value=10000), \
             patch("combat.handle_pvp_defeat") as defeat:
            commands.cmd_finish_downed_yes(self.caster, [])
        self.assertFalse(self.attacker.bloodline_mangekyo)
        self.assertIsNone(self.attacker.mangekyo_eye_1)
        self.assertIsNone(self.victim.downed_by)
        self.assertEqual(storage.load_account("Caster").mangekyo_lock_until,
                         10000 + 7 * 24 * 3600)
        self.assertEqual(self.target.account.mangekyo_lock_until, 0)
        self.caster.request_close.assert_called_once_with()
        defeat.assert_called_once_with(winner_session=self.caster,
                                       loser_session=self.target,
                                       skip_mangekyo_check=True)
        self.assertIn("seven days", self.caster.send.call_args.args[0])

    def test_unknown_ip_fails_closed_without_penalty(self):
        self.target.connection_ip = None
        with patch("combat.handle_pvp_defeat") as defeat:
            commands.cmd_finish_downed_yes(self.caster, [])
        self.assertFalse(self.attacker.bloodline_mangekyo)
        self.assertEqual(storage.load_account("Caster").mangekyo_lock_until, 0)
        self.caster.request_close.assert_not_called()
        defeat.assert_called_once()

    def test_verified_distinct_ips_award_eyes_without_lock(self):
        with patch("data_mangekyo.roll_two_eye_techniques",
                   return_value=("amaterasu", "kamui")), \
             patch("commands.time.time", return_value=12345):
            commands.cmd_finish_downed_yes(self.caster, [])
        self.assertTrue(self.attacker.bloodline_mangekyo)
        self.assertEqual((self.attacker.mangekyo_eye_1, self.attacker.mangekyo_eye_2),
                         ("amaterasu", "kamui"))
        self.assertEqual(self.victim.frozen_until, 12345 + 86400)
        self.assertEqual(storage.load_account("Caster").mangekyo_lock_until, 0)

    def test_suspension_rejects_login_even_with_correct_password(self):
        self.account.mangekyo_lock_until = 10000 + guard.LOCK_SECONDS
        storage.save_account(self.account)
        login = session_module.Session(Mock(), Mock(), connection_ip="192.0.2.10")
        login._pending_name = "Caster"
        login.state = session_module.State.LOGIN_PASSWORD
        with patch("session.time.time", return_value=10001), \
             patch("security.verify_password") as verify:
            login._handle_login_password("correct password")
        self.assertEqual(login.state, session_module.State.CLOSED)
        verify.assert_not_called()

    def test_suspension_expiry_allows_normal_login_attempt(self):
        self.account.mangekyo_lock_until = 10000
        storage.save_account(self.account)
        login = session_module.Session(Mock(), Mock(), connection_ip="192.0.2.10")
        login._pending_name = "Caster"
        login.state = session_module.State.LOGIN_PASSWORD
        with patch("session.time.time", return_value=10001), \
             patch("security.verify_password", return_value=False):
            login._handle_login_password("incorrect password")
        self.assertEqual(login.state, session_module.State.LOGIN_PASSWORD)


if __name__ == "__main__":
    unittest.main()
