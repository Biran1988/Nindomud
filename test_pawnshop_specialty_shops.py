"""Premium gatherer buyers and persistent per-shopkeeper pawnbroker stock."""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_shops
import inventory
import item_types
import olc
import pawnshops
import shop_flags
import storage
from models import Player


class PawnshopTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.room = 98321
        self.template = combat.default_template(98322, "pawn broker")
        shop_flags.set_type(self.template, "pawnshop")
        self.mob = NS(template_vnum=98322, room_vnum=self.room,
                      name="pawn broker", player_shop_owner=None)
        self.protos = {
            98323: dict(olc.default_object(98323, "An Iron Ore"), cost=200),
            98324: dict(olc.default_object(98324, "A Chakra Steel Heartwood Pickaxe"), cost=5000),
            98325: dict(olc.default_object(98325, "A Worthless Rock"), cost=0),
        }
        for p in (
            patch.object(storage, "DATA_DIR", tmp.name),
            patch.object(storage, "PLAYERS_DIR", os.path.join(tmp.name, "players")),
            patch.object(storage, "ACCOUNTS_DIR", os.path.join(tmp.name, "accounts")),
            patch.object(combat, "MOB_TEMPLATES", {98322: self.template}),
            patch.object(olc, "OBJECT_TEMPLATES", self.protos),
            patch.object(commands, "_find_shopkeeper", return_value=self.mob),
            patch.object(commands, "_fire_item_trigger"),
        ):
            p.start(); self.addCleanup(p.stop)
        self.seller = Player("PawnSeller", "PawnSeller", room_vnum=self.room)
        self.seller.ryo = 20
        self.seller.inventory = ["An Iron Ore", "An Iron Ore"]
        self.session = NS(player=self.seller, send=Mock())

    def test_single_pawn_sale_and_buyback_are_real_individual_stock(self):
        commands.cmd_sell(self.session, ["ore"])
        self.assertEqual(self.seller.inventory, ["An Iron Ore"])
        self.assertEqual(self.seller.ryo, 30)  # 200 * 10% * 50% = 10
        saved = pawnshops.stock(self.mob)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["price"], 15)
        self.assertEqual(saved[0]["paid"], 10)
        self.assertTrue(os.path.isfile(pawnshops._path()))
        self.session.send.reset_mock()
        commands.cmd_list(self.session, [])
        self.assertIn("15 ryo", self.session.send.call_args.args[0])
        commands.cmd_buy(self.session, ["ore"])
        self.assertEqual(self.seller.inventory, ["An Iron Ore", "An Iron Ore"])
        self.assertEqual(self.seller.ryo, 15)
        self.assertEqual(pawnshops.stock(self.mob), [])
        # No infinite stock as with an ordinary NPC template shop.
        commands.cmd_buy(self.session, ["ore"])
        self.assertIn("doesn't have", self.session.send.call_args.args[0])
        self.assertEqual(storage.load_player("PawnSeller").ryo, 15)

    def test_other_player_can_buy_from_same_pawnshop(self):
        commands.cmd_sell(self.session, ["ore"])
        buyer = Player("PawnBuyer", "PawnBuyer", room_vnum=self.room)
        buyer.ryo = 100
        session = NS(player=buyer, send=Mock())
        commands.cmd_buy(session, ["ore"])
        self.assertEqual(buyer.inventory, ["An Iron Ore"])
        self.assertEqual(buyer.ryo, 85)
        self.assertEqual(pawnshops.stock(self.mob), [])

    def test_bulk_pawn_and_buy_all_with_finite_stock(self):
        self.seller.inventory = ["An Iron Ore"] * 3 + ["A Worthless Rock"]
        commands.cmd_sell(self.session, ["all", "ore"])
        self.assertEqual(self.seller.ryo, 50)
        self.assertEqual(len(pawnshops.stock(self.mob)), 3)
        self.assertEqual(self.seller.inventory, ["A Worthless Rock"])
        commands.cmd_sell(self.session, ["rock"])
        self.assertIn("no value", self.session.send.call_args.args[0].lower())
        commands.cmd_buy(self.session, ["2", "ore"])
        self.assertEqual(len(pawnshops.stock(self.mob)), 1)
        self.assertEqual(self.seller.ryo, 20)
        commands.cmd_buy(self.session, ["all", "ore"])
        self.assertEqual(pawnshops.stock(self.mob), [])
        self.assertEqual(self.seller.ryo, 5)

    def test_pawnshops_are_isolated_by_mob_and_room(self):
        commands.cmd_sell(self.session, ["ore"])
        different_room = NS(template_vnum=98322, room_vnum=98399,
                            name="pawn broker", player_shop_owner=None)
        self.assertEqual(pawnshops.stock(different_room), [])
        self.assertEqual(len(pawnshops.stock(self.mob)), 1)

    def test_diamond_enhanced_tools_keep_exact_worn_durability(self):
        tool = "A Chakra Steel Heartwood Pickaxe [diamond] [711/2000 uses]"
        self.seller.inventory = [tool]
        commands.cmd_sell(self.session, ["pickaxe"])
        self.assertEqual(pawnshops.stock(self.mob)[0]["item_name"], tool)
        buyer = Player("ToolBuyer", "ToolBuyer", room_vnum=self.room)
        buyer.ryo = 9999
        commands.cmd_buy(NS(player=buyer, send=Mock()), ["pickaxe"])
        self.assertEqual(buyer.inventory, [tool])

    def test_filled_bags_and_soulbound_quest_items_are_not_pawned(self):
        import iron_ascension
        self.seller.inventory = ["An Iron Ore", "A Full Backpack", iron_ascension.HEART]
        self.seller.backpack_contents = {"1": ["A Cut Diamond"]}
        commands.cmd_sell(self.session, ["all", "backpack"])
        self.assertEqual(self.seller.inventory[1], "A Full Backpack")
        self.assertEqual(self.seller.backpack_contents, {"1": ["A Cut Diamond"]})
        commands.cmd_sell(self.session, ["heart"])
        self.assertEqual(len(pawnshops.stock(self.mob)), 0)
        self.assertEqual(self.seller.ryo, 20)


class SpecialtyShopTests(unittest.TestCase):
    def setUp(self):
        self.t = combat.default_template(99100, "material merchant")
        shop_flags.enable_shopkeeper(self.t)
        self.mob = NS(template_vnum=99100, room_vnum=99099,
                      name="material merchant", player_shop_owner=None)
        self.p = Player("MaterialSeller", "MaterialSeller", room_vnum=99099)
        self.session = NS(player=self.p, send=Mock())
        self.protos = {
            i: dict(olc.default_object(i, name), cost=200)
            for i, name in enumerate(("An Iron Ore", "A Sturdy Oak Log", "A Rough Quartz",
                                      "A Carrot", "A Minnow", "A Steel Sword", "Medicinal Herbs"), 99101)
        }
        for pa in (patch.object(combat, "MOB_TEMPLATES", {99100: self.t}),
                   patch.object(olc, "OBJECT_TEMPLATES", self.protos),
                   patch.object(commands, "_find_shopkeeper", return_value=self.mob)):
            pa.start(); self.addCleanup(pa.stop)

    def test_builder_shop_types_and_item_categories(self):
        expected = {"An Iron Ore": "ore", "A Sturdy Oak Log": "wood",
                    "A Rough Quartz": "gem", "A Carrot": "food", "A Minnow": "food"}
        for name, group in expected.items():
            with self.subTest(name=name):
                self.assertEqual(item_types.classify_item(name), group)
        for kind in ("mining", "farming", "lumberjack", "gemcutter", "pawnshop"):
            self.assertIn(kind, data_shops.SHOP_TYPES)
        self.assertTrue(data_shops.can_buy_item("farming", "a carrot", "food"))
        self.assertFalse(data_shops.can_buy_item("farming", "a minnow", "food"))
        self.assertTrue(data_shops.can_buy_item("farming", "medicinal herbs", "misc"))
        self.assertFalse(data_shops.can_buy_item("gemcutter", "an iron ore", "ore"))

    def test_each_specialty_pays_50_percent_more_than_normal_specialty(self):
        cases = (("mining", "An Iron Ore"), ("lumberjack", "A Sturdy Oak Log"),
                 ("gemcutter", "A Rough Quartz"), ("farming", "A Carrot"))
        for kind, item in cases:
            with self.subTest(kind=kind):
                shop_flags.set_type(self.t, kind)
                self.p.inventory = [item]
                self.p.ryo = 0
                commands.cmd_sell(self.session, [item.split()[-1]])
                self.assertEqual(self.p.ryo, 30)  # proto cost 200 -> base 20 * 1.5
                self.assertEqual(self.p.inventory, [])
        shop_flags.set_type(self.t, "farming")
        self.p.inventory = ["A Minnow", "A Carrot"]
        commands.cmd_sell(self.session, ["minnow"])
        self.assertIn("doesn't buy", self.session.send.call_args.args[0])
        self.assertEqual(self.p.inventory, ["A Minnow", "A Carrot"])


if __name__ == "__main__":
    unittest.main()
