"""Bulk buying uses the same item/quantity targeting as bulk selling."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import content
import combat
import inventory
import olc
import playershops
from models import Player


class BulkBuyTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("BulkBuyer", "BulkBuyer", room_vnum=79991)
        self.player.ryo = 20000
        self.session = NS(player=self.player, send=Mock())
        self.raw = olc.default_object(79992, "a sardine")
        self.raw["cost"] = 7
        self.minnow = olc.default_object(79993, "a minnow")
        self.minnow["cost"] = 9
        self.shop = {"type": "food", "items": [
            {"name": "a sardine", "price": 7}, {"name": "a minnow", "price": 9}
        ]}
        self.patches = [
            patch.object(content, "SHOPS", {79991: self.shop}),
            patch.object(commands, "_find_shopkeeper", return_value=None),
            patch.object(commands, "_own_kage_chamber", return_value=False),
            patch.object(commands, "_fire_item_trigger"),
            patch.object(olc, "OBJECT_TEMPLATES", {79992: self.raw, 79993: self.minnow}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_buy_three_sardines_only(self):
        commands.cmd_buy(self.session, ["3", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine"] * 3)
        self.assertEqual(self.player.ryo, 19979)
        self.assertIn("3 item(s)", self.session.send.call_args.args[0])

    def test_buy_all_maxes_out_one_stack_and_not_unrelated_items(self):
        commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine"] * inventory.MAX_STACK_SIZE)
        self.assertEqual(self.player.ryo, 20000 - 7 * inventory.MAX_STACK_SIZE)

    def test_buy_all_when_ryo_runs_out_only_buys_affordable_units(self):
        self.player.ryo = 20
        commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine", "a sardine"])
        self.assertEqual(self.player.ryo, 6)
        self.assertIn("can't afford", self.session.send.call_args.args[0])

    def test_buy_all_does_not_buy_anything_without_item_name(self):
        commands.cmd_buy(self.session, ["all"])
        self.assertEqual(self.player.inventory, [])
        self.assertEqual(self.player.ryo, 20000)
        self.assertIn("buy all <item>", self.session.send.call_args.args[0])

    def test_buy_cannot_exceed_inventory_slot_or_stack_limits(self):
        self.player.inventory = [f"item {i}" for i in range(inventory.MAX_INVENTORY_SLOTS)]
        commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(len(self.player.inventory), inventory.MAX_INVENTORY_SLOTS)
        self.assertEqual(self.player.ryo, 20000)
        self.player.inventory = ["a sardine"] * (inventory.MAX_STACK_SIZE - 1)
        commands.cmd_buy(self.session, ["3", "sardine"])
        self.assertEqual(len(self.player.inventory), inventory.MAX_STACK_SIZE)
        self.assertEqual(self.player.ryo, 19993)

    def test_bulk_buy_must_obey_level_requirements(self):
        self.raw["level"] = self.player.level + 10
        commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, [])
        self.assertEqual(self.player.ryo, 20000)
        self.assertIn("must be level", self.session.send.call_args.args[0])

    def test_npc_shop_bulk_buy_uses_template_price(self):
        mob = NS(name="fishmonger", template_vnum=79994, player_shop_owner=None)
        with patch.object(commands, "_find_shopkeeper", return_value=mob), \
             patch.object(combat, "mob_shop_items", return_value=[79992, 79993]):
            commands.cmd_buy(self.session, ["3", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine"] * 3)
        self.assertEqual(self.player.ryo, 19979)

    def test_player_shop_buys_actual_finite_stock_and_pays_owner(self):
        owner = Player("ShopOwner", "ShopOwner", room_vnum=79991)
        owner.ryo = 40
        owner.shop_stock = [
            {"item_name": "a sardine", "price": 11},
            {"item_name": "a minnow", "price": 5},
            {"item_name": "a sardine", "price": 12},
        ]
        mob = NS(name="ShopOwner's shopkeeper", player_shop_owner=owner.name)
        with patch.object(commands, "_find_shopkeeper", return_value=mob), \
             patch.object(playershops, "_find_owner_player", return_value=(owner, True)):
            commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine"] * 2)
        self.assertEqual(self.player.ryo, 19977)
        self.assertEqual(owner.ryo, 63)
        self.assertEqual(owner.shop_stock, [{"item_name": "a minnow", "price": 5}])

    def test_player_shop_partial_purchase_when_cannot_afford_remaining(self):
        owner = Player("ShopOwner", "ShopOwner", room_vnum=79991)
        owner.shop_stock = [{"item_name": "a sardine", "price": 7}] * 3
        self.player.ryo = 15
        mob = NS(name="ShopOwner's shopkeeper", player_shop_owner=owner.name)
        with patch.object(commands, "_find_shopkeeper", return_value=mob), \
             patch.object(playershops, "_find_owner_player", return_value=(owner, True)):
            commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine"] * 2)
        self.assertEqual(self.player.ryo, 1)
        self.assertEqual(len(owner.shop_stock), 1)

    def test_bulk_does_not_purchase_kage_relics_or_apartments(self):
        self.shop["items"].append({"name": "apartment decoration", "price": 3})
        with patch.object(commands, "_own_kage_chamber", return_value=True):
            commands.cmd_buy(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, [])
        commands.cmd_buy(self.session, ["all", "apartment decoration"])
        self.assertEqual(self.player.inventory, ["apartment decoration"] * inventory.MAX_STACK_SIZE)
        self.assertEqual(self.player.ryo, 20000 - 3 * inventory.MAX_STACK_SIZE)


if __name__ == "__main__":
    unittest.main()
