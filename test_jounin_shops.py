"""Special Jounin and Jounin shops: item VNUMs 39-79, real gameplay perks."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import elemental_counters
import gem_inlays
import item_balance
import jounin_shops
import ninja_arts
import olc
import shop_flags
from models import Player


class JouninShopsTests(unittest.TestCase):
    def setUp(self):
        self.mobs = {
            784: combat.default_template(784, "the Jounin weaponsmith"),
            786: combat.default_template(786, "the Jounin armorsmith"),
        }
        self.mobs[784]["shop_items"] = [9700]
        self.mobs[786]["shop_items"] = [9710]
        self.objects = {}
        for owner, attribute, replacement in (
            (combat, "MOB_TEMPLATES", self.mobs),
            (olc, "OBJECT_TEMPLATES", self.objects),
        ):
            p = patch.object(owner, attribute, replacement)
            p.start()
            self.addCleanup(p.stop)

    def test_full_catalog_levels_auto_balance_elements_and_stock(self):
        result = jounin_shops.install()
        self.assertEqual(result["created"], list(range(39, 80)))
        self.assertEqual(result["shops"], [784, 786])
        self.assertEqual(result["collisions"], [])
        self.assertEqual(self.mobs[784]["shop_items"], [9700] + list(range(39, 60)))
        self.assertEqual(self.mobs[786]["shop_items"], [9710] + list(range(60, 80)))
        self.assertEqual(shop_flags.specialty_from_flags(self.mobs[784]), "weapons")
        self.assertEqual(shop_flags.specialty_from_flags(self.mobs[786]), "blacksmith")

        for vnum, name, level, cost, kind, element in jounin_shops.WEAPONS:
            item = self.objects[vnum]
            with self.subTest(vnum=vnum):
                self.assertEqual((item["short_desc"], item["level"], item["cost"]),
                                 (name, level, cost))
                self.assertEqual(item["item_type"], "weapon")
                self.assertEqual(item["wear_loc"], "wielded")
                self.assertEqual(item["weapon_type"], kind)
                self.assertTrue(item_balance.active(item))
                self.assertIsNone(item["damage"])
                self.assertEqual(item_balance.effective_cost(item), cost)
                if element:
                    self.assertEqual(item["shop_element"], element)
        for vnum, name, level, cost, slot, element in jounin_shops.ARMOR:
            item = self.objects[vnum]
            with self.subTest(vnum=vnum):
                self.assertEqual((item["short_desc"], item["level"], item["cost"]),
                                 (name, level, cost))
                self.assertEqual(item["item_type"], "armor")
                self.assertEqual(item["wear_loc"], slot)
                self.assertTrue(item_balance.active(item))
                self.assertGreater(item_balance.effective_armor_bonus(item), 0)
                if element:
                    self.assertEqual(item["shop_element"], element)
        self.assertEqual({e for *_, e in jounin_shops.WEAPONS if e},
                         set(jounin_shops.ELEMENTS))
        self.assertEqual({e for *_, e in jounin_shops.ARMOR if e},
                         set(jounin_shops.ELEMENTS))
        # Special Jounin begins beyond Chuunin cap (65); Jounin at 200.
        for _v, _n, level, _c, *_ in (*jounin_shops.WEAPONS, *jounin_shops.ARMOR):
            self.assertGreaterEqual(level, 66)
            self.assertLessEqual(level, 250)
        self.assertTrue(any(level < 200 for _v, _n, level, *_ in jounin_shops.WEAPONS))
        self.assertTrue(any(level >= 200 for _v, _n, level, *_ in jounin_shops.WEAPONS))
        self.assertTrue(any(level < 200 for _v, _n, level, *_ in jounin_shops.ARMOR))
        self.assertTrue(any(level >= 200 for _v, _n, level, *_ in jounin_shops.ARMOR))
        self.assertEqual({level for _v, _n, level, _c, _kind, element
                          in jounin_shops.WEAPONS if element}, {175})
        self.assertEqual({level for _v, _n, level, _c, _slot, element
                          in jounin_shops.ARMOR if element}, {160})

    def test_reinstall_preserves_builder_edits_and_original_inventory(self):
        jounin_shops.install()
        self.objects[39]["cost"] = 1234
        self.objects[75]["level"] = 190
        self.mobs[784]["shop_items"].append(333333)
        updated = jounin_shops.install()
        self.assertFalse(updated["created"])
        self.assertEqual(len(updated["preserved"]), 41)
        self.assertEqual(self.objects[39]["cost"], 1234)
        self.assertEqual(self.objects[75]["level"], 190)
        self.assertEqual(self.mobs[784]["shop_items"],
                         [9700] + list(range(39, 60)) + [333333])

    def test_colliding_vnum_is_never_overwritten_or_sold(self):
        occupied = olc.default_object(39, "builder-created relic")
        self.objects[39] = occupied
        updated = jounin_shops.install()
        self.assertIs(self.objects[39], occupied)
        self.assertEqual(updated["collisions"],
                         [(39, "Special Jounin Tanto", "builder-created relic")])
        self.assertNotIn(39, self.mobs[784]["shop_items"])
        self.assertIn(40, self.mobs[784]["shop_items"])

    def test_absent_shopkeepers_are_not_synthesized(self):
        self.mobs.clear()
        updated = jounin_shops.install()
        self.assertEqual(updated["shops"], [])
        self.assertFalse(self.mobs)
        self.assertEqual(updated["created"], list(range(39, 80)))

    def test_elemental_weapons_damage_and_aura_bonuses_are_real(self):
        jounin_shops.install()
        attacker = Player("Attacker", "Attacker")
        victim = Player("Victim", "Victim")
        for vnum, name, _level, _price, _weapon, element in jounin_shops.WEAPONS:
            if not element:
                continue
            with self.subTest(weapon=element):
                attacker.equipment["wielded"] = name
                self.assertEqual(jounin_shops.weapon_element(name), element)
                with patch.object(ninja_arts.samurai_sabre_progression,
                                  "damage_bonus_percent", return_value=0):
                    self.assertEqual(ninja_arts.weapon_hit(attacker, victim, 100), 110)
                self.assertIsNone(jounin_shops.weapon_element("Unrelated " + name))
        for _vnum, name, _level, _price, _slot, element in jounin_shops.ARMOR:
            if not element:
                continue
            with self.subTest(aura=element):
                wearer = Player("AuraUser", "AuraUser")
                wearer.equipment["chakra aura"] = name
                self.assertEqual(jounin_shops.equipped_aura_element(wearer), element)
                self.assertAlmostEqual(
                    gem_inlays.elemental_jutsu_multiplier(wearer, element), 1.10)
                counter = elemental_counters.ELEMENT_COUNTERS[element]
                self.assertEqual(gem_inlays.reduce_counter_damage(wearer, counter, 100), 90)
                another_element = next(
                    e for e in jounin_shops.ELEMENTS if e not in {counter, element})
                self.assertEqual(gem_inlays.reduce_counter_damage(wearer, another_element, 100), 100)
                self.assertAlmostEqual(
                    gem_inlays.elemental_jutsu_multiplier(wearer, another_element), 1.0)

    def test_shop_listing_and_purchase_restrict_jounin_items_by_level(self):
        jounin_shops.install()
        self.mobs[784]["shop_items"] = list(range(39, 60))
        player = Player("GearBuyer", "GearBuyer", room_vnum=878787, level=195)
        player.ryo = 300000
        session = NS(player=player, send=Mock())
        mob = NS(name="the Jounin weaponsmith", template_vnum=784,
                 room_vnum=878787, player_shop_owner=None)
        with patch.object(commands, "_own_kage_chamber", return_value=False), \
             patch.object(commands, "_find_shopkeeper", return_value=mob), \
             patch.object(commands.npc_schedules, "shop_is_open", return_value=True), \
             patch.object(commands, "_fire_item_trigger"):
            commands.cmd_list(session, [])
            listing = session.send.call_args.args[0]
            self.assertIn("Special Jounin Tanto", listing)
            self.assertIn("Emberfang Katana", listing)
            self.assertIn("[Lvl 200]", listing)
            commands.cmd_buy(session, ["12"])
            self.assertIn("must be level 200", session.send.call_args.args[0])
            self.assertEqual(player.inventory, [])
            player.level = 200
            commands.cmd_buy(session, ["12"])
            self.assertIn("Jounin Assassin Dagger", player.inventory)
            self.assertEqual(player.ryo, 228000)


if __name__ == "__main__":
    unittest.main()
