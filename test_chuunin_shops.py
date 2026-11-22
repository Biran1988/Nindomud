"""Chuunin weapon/armor vendor VNUM catalog and saved-world safety checks."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import chuunin_shops
import combat
import commands
import item_balance
import olc
import shop_flags
from models import Player


class ChuuninShopCatalogTests(unittest.TestCase):
    def setUp(self):
        self.mobs = {
            775: combat.default_template(775, "the Chuunin weaponsmith"),
            776: combat.default_template(776, "the Chuunin armorsmith"),
            777: combat.default_template(777, "an unrelated merchant"),
        }
        self.mobs[775]["shop_items"] = [9700]  # Existing stock must remain.
        self.mobs[776]["shop_items"] = [9710]
        self.objects = {}
        for owner, field, replacement in (
            (combat, "MOB_TEMPLATES", self.mobs),
            (olc, "OBJECT_TEMPLATES", self.objects),
        ):
            p = patch.object(owner, field, replacement)
            p.start()
            self.addCleanup(p.stop)

    def test_new_object_ids_levels_and_merchant_stock(self):
        result = chuunin_shops.install()
        self.assertEqual(result["created"], list(range(6, 30)))
        self.assertEqual(result["shops"], [775, 776])
        self.assertEqual(result["collisions"], [])
        self.assertEqual(self.mobs[775]["shop_items"], [9700] + list(range(6, 18)))
        self.assertEqual(self.mobs[776]["shop_items"], [9710] + list(range(18, 30)))
        self.assertEqual(shop_flags.specialty_from_flags(self.mobs[775]), "weapons")
        self.assertEqual(shop_flags.specialty_from_flags(self.mobs[776]), "blacksmith")
        self.assertEqual(self.mobs[777]["shop_items"], [])

        for vnum, name, level, cost, weapon_type in chuunin_shops.WEAPONS:
            item = self.objects[vnum]
            self.assertEqual((item["short_desc"], item["level"], item["cost"]),
                             (name, level, cost))
            self.assertEqual(item["item_type"], "weapon")
            self.assertEqual(item["wear_loc"], "wielded")
            self.assertEqual(item["weapon_type"], weapon_type)
            self.assertTrue(item_balance.active(item))
            self.assertIsNone(item["damage"])
            self.assertEqual(item_balance.effective_cost(item), cost)

        for vnum, name, level, cost, slot in chuunin_shops.ARMOR:
            item = self.objects[vnum]
            self.assertEqual((item["short_desc"], item["level"], item["cost"]),
                             (name, level, cost))
            self.assertEqual(item["item_type"], "armor")
            self.assertEqual(item["wear_loc"], slot)
            self.assertTrue(item_balance.active(item))
            self.assertGreater(item_balance.effective_armor_bonus(item), 0)

    def test_repeated_boots_keep_builder_edits_and_do_not_duplicate_stock(self):
        chuunin_shops.install()
        self.objects[6]["cost"] = 54321  # Builder edits retain priority.
        self.objects[18]["level"] = 42
        self.mobs[775]["shop_items"].append(12345)
        again = chuunin_shops.install()
        self.assertEqual(again["created"], [])
        self.assertEqual(len(again["preserved"]), 24)
        self.assertEqual(self.objects[6]["cost"], 54321)
        self.assertEqual(self.objects[18]["level"], 42)
        self.assertEqual(self.mobs[775]["shop_items"], [9700] + list(range(6, 18)) + [12345])
        self.assertEqual(self.mobs[776]["shop_items"], [9710] + list(range(18, 30)))

    def test_existing_unrelated_object_collision_is_not_clobbered_or_stocked(self):
        occupied = olc.default_object(6, "An Existing Builder Relic")
        occupied["cost"] = 99999
        self.objects[6] = occupied
        result = chuunin_shops.install()
        self.assertIs(self.objects[6], occupied)
        self.assertEqual(occupied["cost"], 99999)
        self.assertNotIn(6, self.mobs[775]["shop_items"])
        self.assertEqual(result["collisions"], [(6, "Reinforced Kunai", "An Existing Builder Relic")])
        self.assertEqual(len(result["created"]), 23)

    def test_existing_matching_item_preserved_and_stocked(self):
        custom = olc.default_object(18, "Reinforced Shinobi Vest")
        custom.update({"item_type": "armor", "wear_loc": "body", "level": 30, "cost": 700})
        self.objects[18] = custom
        result = chuunin_shops.install()
        self.assertIn(18, result["preserved"])
        self.assertIs(self.objects[18], custom)
        self.assertEqual(custom["cost"], 700)
        self.assertIn(18, self.mobs[776]["shop_items"])

    def test_absent_builder_shop_mob_is_not_synthesized(self):
        self.mobs.pop(776)
        result = chuunin_shops.install()
        self.assertEqual(result["shops"], [775])
        self.assertNotIn(776, self.mobs)
        self.assertEqual([i for i in self.objects if 18 <= i <= 29], list(range(18, 30)))

    def test_npc_list_and_purchase_respect_levels_and_numbered_stock(self):
        # Show only the Chuunin stock rather than existing unrelated goods.
        self.mobs[775]["shop_items"] = []
        self.mobs[776]["shop_items"] = []
        chuunin_shops.install()
        player = Player("VendorVisitor", "VendorVisitor", level=20, room_vnum=424242)
        player.ryo = 20000
        session = NS(player=player, send=Mock())
        mob = NS(name="Chuunin weaponsmith", template_vnum=775,
                 room_vnum=424242, player_shop_owner=None)
        with patch.object(commands, "_own_kage_chamber", return_value=False), \
             patch.object(commands, "_find_shopkeeper", return_value=mob), \
             patch.object(commands.npc_schedules, "shop_is_open", return_value=True), \
             patch.object(commands, "_fire_item_trigger"):
            commands.cmd_list(session, [])
            listing = session.send.call_args.args[0]
            self.assertIn("[1] Reinforced Kunai - 750 ryo", listing)
            self.assertIn("[12] Chuunin Elite Blade - 7500 ryo", listing)
            self.assertIn("[Lvl 15]", listing)
            self.assertIn("[Lvl 35]", listing)
            commands.cmd_buy(session, ["12"])
            self.assertIn("must be level 35", session.send.call_args.args[0])
            self.assertEqual(player.inventory, [])
            player.level = 35
            commands.cmd_buy(session, ["12"])
            self.assertIn("Chuunin Elite Blade", player.inventory)
            self.assertEqual(player.ryo, 12500)

        armored = NS(name="Chuunin armorsmith", template_vnum=776,
                     room_vnum=424242, player_shop_owner=None)
        with patch.object(commands, "_own_kage_chamber", return_value=False), \
             patch.object(commands, "_find_shopkeeper", return_value=armored), \
             patch.object(commands.npc_schedules, "shop_is_open", return_value=True), \
             patch.object(commands, "_fire_item_trigger"):
            commands.cmd_list(session, [])
            listing = session.send.call_args.args[0]
            self.assertIn("[1] Reinforced Shinobi Vest - 900 ryo", listing)
            self.assertIn("[12] Chuunin Elite Battle Armor - 7600 ryo", listing)
            self.assertIn("[Lvl 35]", listing)
            commands.cmd_buy(session, ["12"])
            self.assertIn("Chuunin Elite Battle Armor", player.inventory)
            self.assertEqual(player.ryo, 4900)


if __name__ == "__main__":
    unittest.main()
