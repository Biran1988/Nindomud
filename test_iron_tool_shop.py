"""Iron tool merchant VNUM 779, new tool VNUMs 30-38 and craft/gather flow."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import chuunin_shops
import combat
import commands
import cooking
import data_crafting
import farming
import gemcutter
import iron_tool_shop
import olc
import shop_flags
import tool_durability
from models import Player


class IronToolMerchantTests(unittest.TestCase):
    def setUp(self):
        self.mobs = {779: combat.default_template(779, "the tool merchant")}
        self.mobs[779]["shop_items"] = [9700]
        self.objects = {}
        for vnum, name in iron_tool_shop.EXISTING_IRON_TOOLS:
            obj = olc.default_object(vnum, name)
            obj.update({"item_type": "tool", "wear_loc": "tool",
                        "cost": data_crafting.TOOL_RECIPES["iron"]["price"],
                        "max_uses": data_crafting.TOOL_RECIPES["iron"]["uses"]})
            self.objects[vnum] = obj
        self.patchers = [
            patch.object(combat, "MOB_TEMPLATES", self.mobs),
            patch.object(olc, "OBJECT_TEMPLATES", self.objects),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_all_six_iron_tools_sell_and_new_ids_continue_after_armor(self):
        result = iron_tool_shop.install()
        self.assertEqual(result["created"], list(range(30, 39)))
        self.assertEqual(result["stock"], [20002, 20201, 20101, 30, 33, 36])
        self.assertEqual(self.mobs[779]["shop_items"],
                         [9700, 20002, 20201, 20101, 30, 33, 36])
        self.assertTrue(shop_flags.is_shopkeeper_template(self.mobs[779]))
        for vnum, kind, tier in iron_tool_shop.NEW_TOOLS:
            recipe = data_crafting.TOOL_RECIPES[tier]
            proto = self.objects[vnum]
            self.assertEqual(proto["short_desc"], data_crafting.job_tool_name(kind, tier))
            self.assertEqual(proto["item_type"], "tool")
            self.assertEqual(proto["wear_loc"], "tool")
            self.assertEqual(proto["cost"], recipe["price"])
            self.assertEqual(proto["max_uses"], recipe["uses"])
            self.assertEqual(tool_durability.uses_left(proto["short_desc"]),
                             (recipe["uses"], recipe["uses"]))

    def test_repeated_reboots_preserve_saved_stock_and_edited_gear(self):
        iron_tool_shop.install()
        self.objects[30]["max_uses"] = 999
        self.objects[34]["cost"] = 333
        self.mobs[779]["shop_items"].append(442)
        again = iron_tool_shop.install()
        self.assertFalse(again["created"])
        self.assertEqual(len(again["preserved"]), 9)
        self.assertEqual(self.objects[30]["max_uses"], 999)
        self.assertEqual(self.objects[34]["cost"], 333)
        self.assertEqual(self.mobs[779]["shop_items"],
                         [9700, 20002, 20201, 20101, 30, 33, 36, 442])

    def test_conflicting_object_ids_are_not_overwritten(self):
        occupied = olc.default_object(30, "a custom builder item")
        self.objects[30] = occupied
        result = iron_tool_shop.install()
        self.assertIs(self.objects[30], occupied)
        self.assertEqual(result["collisions"],
                         [(30, "An Ironbound Oak Hoe", "a custom builder item")])
        self.assertNotIn(30, self.mobs[779]["shop_items"])
        self.assertIn(33, self.mobs[779]["shop_items"])
        self.assertIn(36, self.mobs[779]["shop_items"])

    def test_absent_mob_is_not_replaced(self):
        self.mobs.clear()
        result = iron_tool_shop.install()
        self.assertFalse(result["shop_exists"])
        self.assertFalse(self.mobs)

    def test_hoe_pot_chisel_are_craftable_from_wood_and_ingot(self):
        iron_tool_shop.install()
        for kind in ("hoe", "pot", "chisel"):
            for tier, recipe in data_crafting.TOOL_RECIPES.items():
                with self.subTest(kind=kind, tier=tier):
                    player = Player("ToolCrafter", "ToolCrafter",
                                    primary_class="bukijutsu", level=100)
                    player.stamina = 500
                    player.inventory = [recipe["wood"], recipe["ingot"]]
                    messages = []
                    session = NS(player=player, send=messages.append,
                                 is_busy=lambda: False,
                                 start_timed_action=lambda _n, _d, action: action())
                    with patch.object(commands.storage, "save_player"):
                        commands.cmd_craft(session, ["tool", kind, tier])
                    name = data_crafting.job_tool_name(kind, tier)
                    self.assertIn(name, player.inventory)
                    self.assertNotIn(recipe["wood"], player.inventory)
                    self.assertNotIn(recipe["ingot"], player.inventory)
                    self.assertEqual(tool_durability.uses_left(name),
                                     (recipe["uses"], recipe["uses"]))

    def test_new_hoes_and_pots_match_farming_and_cooking_job_levels(self):
        self.assertEqual(farming.HOES["an ironbound oak hoe"]["required_level"], 15)
        self.assertEqual(farming.HOES["a steel ironwood hoe"]["required_level"], 35)
        self.assertEqual(farming.HOES["a chakra steel heartwood hoe"]["required_level"], 75)
        self.assertEqual(cooking.POTS["an ironbound oak cooking pot"]["required_level"], 15)
        self.assertEqual(cooking.POTS["a steel ironwood cooking pot"]["required_level"], 35)
        self.assertEqual(cooking.POTS["a chakra steel heartwood cooking pot"]["required_level"], 75)
        with patch("weather.gathering_fail_chance_modifier", return_value=0):
            copper = cooking._burn_chance(15)
            self.assertLess(cooking._burn_chance(15, "An Ironbound Oak Cooking Pot"), copper)
            self.assertLessEqual(cooking._burn_chance(15, "A Steel Ironwood Cooking Pot"),
                                 cooking._burn_chance(15, "An Ironbound Oak Cooking Pot"))
        self.assertEqual(gemcutter.CHISELS["an ironbound oak chisel"]["required_level"], 15)

    def test_npc_shop_listing_and_numbered_buy(self):
        iron_tool_shop.install()
        self.mobs[779]["shop_items"].remove(9700)
        mob = NS(name="the iron tool merchant", template_vnum=779,
                 room_vnum=444, player_shop_owner=None)
        player = Player("IronToolCustomer", "IronToolCustomer", level=25, room_vnum=444)
        player.ryo = 10000
        session = NS(player=player, send=Mock())
        with patch.object(commands, "_own_kage_chamber", return_value=False), \
             patch.object(commands, "_find_shopkeeper", return_value=mob), \
             patch.object(commands.npc_schedules, "shop_is_open", return_value=True), \
             patch.object(commands, "_fire_item_trigger"):
            commands.cmd_list(session, [])
            listing = session.send.call_args.args[0]
            self.assertIn("[1] An Ironbound Oak Fishing Rod", listing)
            self.assertIn("[4] An Ironbound Oak Hoe", listing)
            self.assertIn("[5] An Ironbound Oak Cooking Pot", listing)
            self.assertIn("[6] An Ironbound Oak Chisel", listing)
            commands.cmd_buy(session, ["6"])
            self.assertIn("An Ironbound Oak Chisel", player.inventory)
            self.assertEqual(player.ryo, 10000 - data_crafting.TOOL_RECIPES["iron"]["price"])


if __name__ == "__main__":
    unittest.main()
