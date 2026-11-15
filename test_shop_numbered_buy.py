"""Numbered shop listings and BUY <list-number> selection.

A bare integer chooses one displayed row; a quantity followed by an item
name continues to use the existing bulk purchase path.
"""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import content
import olc
import pawnshops
import playershops
import storage
from models import Player


class NumberedShopBuyTests(unittest.TestCase):
    def setUp(self):
        self.room = 97941
        self.player = Player("NumberBuyer", "NumberBuyer", room_vnum=self.room)
        self.player.ryo = 1000
        self.session = NS(player=self.player, send=Mock())
        self.stock = {
            97942: dict(olc.default_object(97942, "a sardine"), cost=7),
            97943: dict(olc.default_object(97943, "a minnow"), cost=9),
        }
        self.legacy = {"type": "food", "items": [
            {"name": "a sardine", "price": 7},
            {"name": "a minnow", "price": 9},
        ]}
        self.active_shopkeeper = None
        for obj, name, value in (
                (olc, "OBJECT_TEMPLATES", self.stock),
                (content, "SHOPS", {self.room: self.legacy}),
                (commands, "_own_kage_chamber", Mock(return_value=False)),
                (commands, "_find_shopkeeper", Mock(side_effect=lambda room: self.active_shopkeeper)),
                (commands, "_fire_item_trigger", Mock()),
                (commands.npc_schedules, "shop_is_open", Mock(return_value=True))):
            p = patch.object(obj, name, value)
            p.start()
            self.addCleanup(p.stop)

    def shown(self):
        self.session.send.reset_mock()
        commands.cmd_list(self.session, [])
        return self.session.send.call_args.args[0]

    def buy(self, *args):
        self.session.send.reset_mock()
        commands.cmd_buy(self.session, list(args))
        return self.session.send.call_args.args[0]

    def test_legacy_store_numbers_select_exact_row_and_keep_bulk_buy(self):
        listing = self.shown()
        self.assertIn("[1] a sardine", listing)
        self.assertIn("[2] a minnow", listing)
        self.assertIn("BUY <number>", listing)
        self.buy("2")
        self.assertEqual(self.player.inventory, ["a minnow"])
        self.assertEqual(self.player.ryo, 991)
        result = self.buy("0")
        self.assertIn("Type LIST", result)
        self.assertEqual(self.player.ryo, 991)
        self.buy("2", "sardine")
        self.assertEqual(self.player.inventory, ["a minnow", "a sardine", "a sardine"])
        self.assertEqual(self.player.ryo, 977)
        self.buy("sardine")
        self.assertEqual(self.player.inventory[-1], "a sardine")

    def test_npc_shop_skips_missing_prototypes_and_enforces_item_level(self):
        self.active_shopkeeper = NS(name="fish seller", player_shop_owner=None,
                                    template_vnum=97944)
        self.stock[97943]["level"] = 10
        with patch.object(combat, "mob_shop_items", return_value=[99999, 97942, 97943]), \\
             patch.object(combat, "mob_shop_buys_categories", return_value=[]), \\
             patch.object(combat, "MOB_TEMPLATES", {97944: {}}):
            listing = self.shown()
            self.assertIn("[1] a sardine", listing)
            self.assertIn("[2] a minnow", listing)
            self.assertNotIn("[3]", listing)
            warning = self.buy("2")
            self.assertIn("must be level", warning)
            self.assertEqual(self.player.ryo, 1000)
            self.stock[97943]["level"] = 0
            self.buy("2")
            self.assertEqual(self.player.inventory, ["a minnow"])
            self.assertEqual(self.player.ryo, 991)
            warning = self.buy("3")
            self.assertIn("Type LIST", warning)
            self.assertEqual(self.player.inventory, ["a minnow"])

    def test_player_shop_indices_skip_unpriced_and_select_exact_copy(self):
        owner = Player("Seller", "Seller", room_vnum=self.room)
        owner.shop_stock = [
            {"item_name": "a sardine", "price": None},
            {"item_name": "a sardine", "price": 11},
            {"item_name": "a sardine", "price": 29},
        ]
        self.active_shopkeeper = NS(name="Seller's shopkeeper",
                                    player_shop_owner="Seller")
        with patch.object(playershops, "_find_owner_player", return_value=(owner, True)):
            listing = self.shown()
            self.assertIn("[1] a sardine - 11 ryo", listing)
            self.assertIn("[2] a sardine - 29 ryo", listing)
            self.assertNotIn("no price set", listing)
            self.buy("2")
            self.assertEqual(self.player.ryo, 971)
            self.assertEqual(owner.ryo, 29)
            self.assertEqual([row["price"] for row in owner.shop_stock], [None, 11])
            self.assertEqual(self.player.inventory, ["a sardine"])
            again = self.shown()
            self.assertIn("[1] a sardine - 11 ryo", again)
            self.assertNotIn("[2]", again)
            warning = self.buy("2")
            self.assertIn("Type LIST", warning)
            self.assertEqual(self.player.ryo, 971)

    def test_pawnshop_numbers_select_individual_same_name_prices(self):
        mob = NS(name="pawnbroker", player_shop_owner=None, template_vnum=97945)
        self.active_shopkeeper = mob
        state = {pawnshops.key(mob, self.room): [
            {"item_name": "a sardine", "price": 11},
            {"item_name": "a sardine", "price": 29},
        ]}
        with patch.object(pawnshops, "is_pawnshop", return_value=True), \\
             patch.object(pawnshops, "_load", return_value=state), \\
             patch.object(pawnshops, "_save"), \\
             patch.object(storage, "save_player"):
            listing = self.shown()
            self.assertIn("[1] a sardine - 11 ryo", listing)
            self.assertIn("[2] a sardine - 29 ryo", listing)
            self.buy("2")
            self.assertEqual(self.player.ryo, 971)
            self.assertEqual(self.player.inventory, ["a sardine"])
            self.assertEqual(state[pawnshops.key(mob, self.room)],
                             [{"item_name": "a sardine", "price": 11}])
            warning = self.buy("2")
            self.assertIn("Type LIST", warning)
            self.assertEqual(self.player.ryo, 971)


if __name__ == "__main__":
    unittest.main()
