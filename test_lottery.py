"""Daily draw, rollover, split payout, and bank alias."""

import tempfile
import unittest
from unittest.mock import patch

import lottery
import storage
from models import Player


class LotteryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for key, value in (("DATA_DIR", directory.name),
                           ("PLAYERS_DIR", directory.name + "/players"),
                           ("ACCOUNTS_DIR", directory.name + "/accounts")):
            p = patch.object(storage, key, value)
            p.start()
            self.addCleanup(p.stop)

    def test_rollover_and_matching_ticket_pays_bank_then_resets(self):
        a = Player("Alpha", "Alpha", ryo=5000)
        b = Player("Bravo", "Bravo", ryo=5000)
        self.assertIsNone(lottery.buy(a, "0042", now=100))
        self.assertIsNone(lottery.buy(b, "0042", now=100))
        self.assertEqual(lottery.load()["jackpot"], 27000)
        with patch("lottery.secrets.randbelow", return_value=9999):
            state = lottery.draw_due(now=100 + lottery.DRAW_INTERVAL)
        self.assertEqual(state["jackpot"], 52000)
        self.assertEqual(state["tickets"], [])
        self.assertIsNone(lottery.buy(a, "0042", now=101 + lottery.DRAW_INTERVAL))
        self.assertIsNone(lottery.buy(b, "0042", now=101 + lottery.DRAW_INTERVAL))
        with patch("lottery.secrets.randbelow", return_value=42):
            state = lottery.draw_due(now=100 + 2 * lottery.DRAW_INTERVAL)
        self.assertEqual(state["jackpot"], 25000)
        self.assertEqual(storage.load_player("Alpha").bank_balance, 27000)
        self.assertEqual(storage.load_player("Bravo").bank_balance, 27000)

    def test_rejects_invalid_number_and_insufficient_funds(self):
        player = Player("Alpha", "Alpha", ryo=999)
        self.assertIsNotNone(lottery.buy(player, "42", now=100))
        self.assertIsNotNone(lottery.buy(player, "0042", now=100))
        self.assertEqual(player.ryo, 999)

    def test_one_ticket_per_draw_and_random_pick_preserves_leading_zeroes(self):
        player = Player("Alpha", "Alpha", ryo=5000)
        with patch("lottery.secrets.randbelow", return_value=42):
            self.assertIsNone(lottery.buy(player, "random", now=100))
        self.assertEqual(lottery.load()["tickets"], [{"player": "Alpha", "number": "0042"}])
        self.assertIn("already have a ticket", lottery.buy(player, "1234", now=101))
        self.assertEqual(player.ryo, 4000)
        self.assertEqual(lottery.load()["jackpot"], 26000)
        with patch("lottery.secrets.randbelow", return_value=9999):
            lottery.draw_due(now=100 + lottery.DRAW_INTERVAL)
        self.assertIsNone(lottery.buy(player, "1234", now=101 + lottery.DRAW_INTERVAL))
        self.assertEqual(player.ryo, 3000)


if __name__ == "__main__":
    unittest.main()
