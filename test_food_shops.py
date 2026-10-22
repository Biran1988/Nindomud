"""Food specialty shop type: raw/cooked food, live builder shops, Ryo payouts."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_shops
import item_types
import olc
from models import Player


class FoodShopTests(unittest.TestCase):
    def setUp(self):
        self.shopkeeper = combat.default_template(9002, "food merchant")
        self.shopkeeper["shopkeeper"] = True
        self.mob = NS(name="food merchant", template_vnum=9002, player_shop_owner=None)
        raw = olc.default_object(9100, "A Swordfish")
        raw.update(item_type="misc", cost=300)
        crop = olc.default_object(9101, "A Watermelon")
        crop.update(item_type="food", cost=100)
        cooked = olc.default_object(9102, "A Cooked Salmon")
        cooked.update(item_type="food", cost=200)
        sword = olc.default_object(9103, "A Steel Sword")
        sword.update(item_type="weapon", weapon_type="sword", cost=400)
        self.patches = [
            patch.object(combat, "MOB_TEMPLATES", {9002: self.shopkeeper}),
            patch.object(olc, "OBJECT_TEMPLATES",
                         {9100: raw, 9101: crop, 9102: cooked, 9103: sword}),
            patch.object(commands, "_find_shopkeeper", return_value=self.mob),
            patch.object(olc, "_log", Mock()),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.player = Player("FoodTester", "FoodTester", room_vnum=9001)
        self.player.ryo = 15
        self.session = NS(player=self.player, send=Mock(),
                          account=NS(staff_level="implementor"))

    def test_food_specialty_registered_without_changing_other_shop_types(self):
        self.assertEqual(data_shops.SHOP_TYPES["food"]["display_name"], "Food Shop")
        self.assertTrue(data_shops.can_sell_here("food", "food"))
        self.assertFalse(data_shops.can_sell_here("food", "weapon"))
        self.assertEqual(data_shops.sell_multiplier("food"), 1.0)
        self.assertEqual(data_shops.sell_multiplier("general"), 0.5)

    def test_cooked_uncooked_farm_and_builder_food_are_recognized(self):
        for name in ("a swordfish", "A Salmon", "A Minnow", "A Watermelon",
                     "a carrot", "A Cooked Salmon", "A Cooked Swordfish",
                     "A Leviathan Fillet", "a bowl of ramen"):
            with self.subTest(name=name):
                self.assertEqual(item_types.classify_item(name), "food")
        custom_food = olc.default_object(9110, "A Special Festival Bento")
        custom_food["item_type"] = "food"
        olc.OBJECT_TEMPLATES[9110] = custom_food
        self.assertEqual(item_types.classify_item("A Special Festival Bento"), "food")
        self.assertEqual(item_types.classify_item("A Steel Sword"), "weapon")

    def test_builder_can_configure_food_only_shop(self):
        olc.cmd_mset(self.session, ["9002", "shopkeeper", "on"])
        olc.cmd_mset(self.session, ["9002", "shoptype", "food"])
        self.assertEqual(self.shopkeeper["shop_type"], "food")
        self.assertEqual(combat.mob_shop_buys_categories(self.mob), ["food"])
        commands.cmd_list(self.session, [])
        self.assertIn("Only buys food", self.session.send.call_args.args[0])
        olc.cmd_mset(self.session, ["9002", "shoptype"])
        self.assertIn("food", self.session.send.call_args.args[0])

    def test_food_shop_pays_full_specialty_price_and_rejects_weapons(self):
        self.shopkeeper["shop_type"] = "food"
        self.player.inventory = ["A Swordfish", "A Cooked Salmon", "A Watermelon",
                                 "A Steel Sword"]
        commands.cmd_sell(self.session, ["swordfish"])
        self.assertEqual(self.player.ryo, 45)  # raw fish prototype 300 * 10%
        commands.cmd_sell(self.session, ["cooked", "salmon"])
        self.assertEqual(self.player.ryo, 245)  # cooking.py dish payout 200
        commands.cmd_sell(self.session, ["watermelon"])
        self.assertEqual(self.player.ryo, 255)  # crop prototype 100 * 10%
        commands.cmd_sell(self.session, ["steel", "sword"])
        self.assertIn("doesn't buy weapon", self.session.send.call_args.args[0])
        self.assertEqual(self.player.ryo, 255)
        self.assertEqual(self.player.inventory, ["A Steel Sword"])

    def test_general_store_still_pays_half_for_raw_food(self):
        self.player.inventory = ["A Swordfish"]
        commands.cmd_sell(self.session, ["swordfish"])
        self.assertEqual(self.player.ryo, 30)  # half of raw fish 30 Ryo
        self.assertEqual(self.player.inventory, [])

    def test_existing_manual_specialty_and_switching_type(self):
        self.shopkeeper["shop_buys_categories"] = ["weapon"]
        self.assertEqual(combat.mob_shop_buys_categories(self.mob), ["weapon"])
        olc.cmd_mset(self.session, ["9002", "shoptype", "food"])
        self.assertEqual(self.shopkeeper["shop_buys_categories"], [])
        self.assertEqual(combat.mob_shop_buys_categories(self.mob), ["food"])
        olc.cmd_mset(self.session, ["9002", "shoptype", "nonsense"])
        self.assertEqual(self.shopkeeper["shop_type"], "food")
        self.assertIn("Shop types:", self.session.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
