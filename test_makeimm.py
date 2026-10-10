"""Account promotion permissions and persistence."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import commands
import storage
from models import Account


class FakeSession:
    def __init__(self, name, rank):
        self.account = Account(name, "salt", "hash", staff_level=rank)
        self.player = SimpleNamespace(_immortal_skill_mastery=False)
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class MakeImmTests(unittest.TestCase):
    def test_higher_rank_promotion_is_owner_only_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                storage.save_account(Account("Kakashi", "salt", "hash", staff_level="helper"))
                target = FakeSession("Kakashi", "helper")
                owner = FakeSession("biran", "implementor")
                with patch("session.ACTIVE_SESSIONS", [target]):
                    commands.cmd_promoteimm(FakeSession("Other", "implementor"), ["Kakashi", "builder"])
                    commands.cmd_promoteimm(owner, ["Kakashi", "implementor"])
                    self.assertEqual(storage.load_account("Kakashi").staff_level, "helper")
                    commands.cmd_promoteimm(owner, ["Kakashi", "builder"])
                    self.assertEqual(target.account.staff_level, "builder")
                    commands.cmd_promoteimm(owner, ["Kakashi", "area", "leader"])
                    commands.cmd_promoteimm(owner, ["Kakashi", "administrator"])
                    commands.cmd_promoteimm(owner, ["Kakashi", "builder"])
                self.assertEqual(storage.load_account("Kakashi").staff_level, "administrator")
                self.assertEqual(storage.load_account("Kakashi").hash_hex, "hash")

    def test_only_biran_promotes_an_existing_player_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")), \
                 patch("session.ACTIVE_SESSIONS", []):
                storage.save_account(Account("Kakashi", "salt", "hash"))
                denied = FakeSession("Other", "implementor")
                commands.cmd_makeimm(denied, ["Kakashi"])
                self.assertEqual(storage.load_account("Kakashi").staff_level, "player")
                owner = FakeSession("biran", "implementor")
                commands.cmd_makeimm(owner, ["../Kakashi"])
                self.assertEqual(storage.load_account("Kakashi").staff_level, "player")
                commands.cmd_makeimm(owner, ["Missing"])
                self.assertFalse(storage.account_exists("Missing"))
                commands.cmd_makeimm(owner, ["Kakashi"])
                self.assertEqual(storage.load_account("Kakashi").staff_level, "helper")
                commands.cmd_makeimm(owner, ["Kakashi"])
                self.assertEqual(storage.load_account("Kakashi").staff_level, "helper")

    def test_online_account_updates_without_replacing_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                storage.save_account(Account("Kakashi", "salt", "hash"))
                target = FakeSession("Kakashi", "player")
                with patch("session.ACTIVE_SESSIONS", [target]):
                    commands.cmd_makeimm(FakeSession("biran", "implementor"), ["Kakashi"])
                self.assertEqual(target.account.staff_level, "helper")
                self.assertTrue(target.player._immortal_skill_mastery)
                self.assertEqual(storage.load_account("Kakashi").hash_hex, "hash")


if __name__ == "__main__":
    unittest.main()
