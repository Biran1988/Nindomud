"""Staff SLAY uses a separate confirmation and never deletes staff accounts."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import config
import slay_character
import storage
from models import Account, Player


class SlayCharacterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = [
            patch.object(storage, "DATA_DIR", self.tmp.name),
            patch.object(storage, "ACCOUNTS_DIR", str(Path(self.tmp.name) / "accounts")),
            patch.object(storage, "PLAYERS_DIR", str(Path(self.tmp.name) / "players")),
        ]
        for item in self.paths:
            item.start()
            self.addCleanup(item.stop)
        self.owner = NS(
            account=NS(name=config.ADMIN_NAME, staff_level="implementor"),
            player=Player("Biran", config.ADMIN_NAME),
            send=Mock(),
        )
        self.name = "Kakashi"
        storage.save_account(Account(self.name, "salt", "hash"))
        storage.save_player(Player(self.name, self.name))

    def test_incorrect_confirmation_does_not_delete(self):
        slay_character.command(self.owner, [self.name])
        self.assertTrue(storage.player_exists(self.name))
        self.assertTrue(storage.account_exists(self.name))
        self.assertTrue(slay_character.consume_confirmation(self.owner, "1234"))
        self.assertTrue(storage.player_exists(self.name))
        self.assertTrue(storage.account_exists(self.name))
        self.assertFalse(slay_character.consume_confirmation(self.owner, "1212"))

    def test_confirmation_closes_online_target_before_removing_both_files(self):
        victim = NS(
            player=Player(self.name, self.name),
            account=NS(name=self.name, staff_level="player"),
            send=Mock(), request_close=Mock(),
        )
        slay_character.command(self.owner, [self.name])
        with (patch("session.ACTIVE_SESSIONS", [victim]),
              patch("olc._log") as audit):
            self.assertTrue(slay_character.consume_confirmation(self.owner, "1212"))
        victim.request_close.assert_called_once()
        audit.assert_called_once()
        self.assertFalse(storage.player_exists(self.name))
        self.assertFalse(storage.account_exists(self.name))

    def test_staff_target_and_non_implementor_cannot_delete(self):
        account = storage.load_account(self.name)
        account.staff_level = "helper"
        storage.save_account(account)
        slay_character.command(self.owner, [self.name])
        self.assertIsNone(self.owner._slay_pending)
        self.assertTrue(storage.player_exists(self.name))
        self.assertTrue(storage.account_exists(self.name))
        account.staff_level = "player"
        storage.save_account(account)
        self.owner.account.staff_level = "administrator"
        slay_character.command(self.owner, [self.name])
        self.assertIsNone(self.owner._slay_pending)
        self.assertTrue(storage.player_exists(self.name))

    def test_confirmation_expires_and_rechecks_account(self):
        slay_character.command(self.owner, [self.name])
        self.owner._slay_pending = (self.name.lower(), time.monotonic() - 1)
        self.assertTrue(slay_character.consume_confirmation(self.owner, "1212"))
        self.assertTrue(storage.player_exists(self.name))
        slay_character.command(self.owner, [self.name])
        # A staff promotion during the confirmation interval must block slay.
        account = storage.load_account(self.name)
        account.staff_level = "builder"
        storage.save_account(account)
        self.assertTrue(slay_character.consume_confirmation(self.owner, "1212"))
        self.assertTrue(storage.player_exists(self.name))


if __name__ == "__main__":
    unittest.main()
