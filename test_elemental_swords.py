"""Regressions for Bukijutsu's persistent elemental sword enchantments."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import content
import data_jutsu
import ninja_arts
import olc
import data_weapons
from models import Player


class TestElementalSword(unittest.TestCase):
    def setUp(self):
        content._register_shared_items()
        self.p = Player("SwordTester", "SwordTester", primary_class="bukijutsu", level=75)
        self.p.chakra_nature = "fire"
        self.p.chakra_nature_revealed = True
        self.p.chakra = self.p.stamina = 1000
        self.p.learned_skills.extend(("Weapon Enchantment", "Disenchantment"))
        # Every positive enchantment case uses an actual Chakra Steel weapon,
        # not merely an arbitrary shop sword or a suggestive item name.
        proto = olc.default_object(999901, "A Forged Chakra Steel Sword")
        proto.update({"item_type": "weapon", "weapon_type": "sword", "wear_loc": "wielded",
                      "craft_materials": ["chakra steel ingot", "yew log"]})
        olc.OBJECT_TEMPLATES[999901] = proto
        self.addCleanup(olc.OBJECT_TEMPLATES.pop, 999901, None)
        self.p.equipment["wielded"] = "A Forged Chakra Steel Sword"
        self.s = NS(player=self.p, send=Mock())

    def enchant(self, element):
        ninja_arts.use_weapon_art(self.s, "weapon enchantment", ["forged", "chakra", "steel", "sword", element])
        return self.p.equipment["wielded"]

    def test_all_five_elements_reuse_the_real_jutsu_effects(self):
        for element, effect, chance in (
            ("fire", "burning", 40), ("water", "drained", 40),
            ("wind", "off_balance", 40), ("lightning", "paralyzed", 30),
            ("earth", None, 0),
        ):
            with self.subTest(element=element):
                self.p.chakra_nature = element
                self.p.cooldowns.clear()
                self.p.equipment["wielded"] = "A Forged Chakra Steel Sword"
                weapon = self.enchant(element)
                self.assertEqual(ninja_arts.element_of(weapon), element)
                self.assertEqual(ninja_arts.base_item(weapon), "A Forged Chakra Steel Sword")
                target = Player("Target", "Target")
                with patch.object(ninja_arts.random, "randint", return_value=1):
                    damage = ninja_arts.weapon_hit(self.p, target, 100)
                self.assertEqual(damage, 187 if element == "earth" else 150)
                self.assertEqual(effect in target.active_status_effects, effect is not None)
                jutsu = data_jutsu.JUTSU[ninja_arts.ELEMENTAL_WEAPON_JUTSU[element]]
                self.assertEqual((jutsu.get("effect"), jutsu.get("effect_chance_pct", 0)), (effect, chance))

    def test_stacks_multiplicatively_with_samurai_sabre(self):
        self.enchant("fire")
        self.p.samurai_sabre_active = True
        with patch.object(ninja_arts.random, "randint", return_value=100):
            self.assertEqual(ninja_arts.weapon_hit(self.p, Player("Target", "Target"), 100), 180)

    def test_earth_stacks_with_sabre_and_has_no_status(self):
        self.p.chakra_nature = "earth"
        self.enchant("earth")
        self.p.samurai_sabre_active = True
        target = Player("Target", "Target")
        self.assertEqual(ninja_arts.weapon_hit(self.p, target, 100), 225)
        self.assertFalse(target.active_status_effects)

    def test_only_matching_bukijutsu_wielder_gets_elemental_effect(self):
        self.enchant("fire")
        target = Player("Target", "Target")
        with patch.object(ninja_arts.random, "randint", return_value=1):
            self.p.chakra_nature = "water"
            self.assertEqual(ninja_arts.weapon_hit(self.p, target, 100), 100)
            self.p.chakra_nature = "fire"
            self.p.primary_class = "ninjutsu"
            self.assertEqual(ninja_arts.weapon_hit(self.p, target, 100), 100)
        self.assertFalse(target.active_status_effects)

    def test_elemental_effect_announces_only_when_it_procs(self):
        expectations = {
            "fire": "ignites",
            "water": "drains",
            "wind": "off balance",
            "lightning": "paralyzes",
            "earth": "crashes",
        }
        for element, fragment in expectations.items():
            with self.subTest(element=element):
                self.p.chakra_nature = element
                self.p.cooldowns.clear()
                self.p.equipment["wielded"] = "A Forged Chakra Steel Sword"
                self.enchant(element)
                self.s.send.reset_mock()
                with patch.object(ninja_arts.random, "randint", return_value=1):
                    ninja_arts.weapon_hit(self.p, Player("Enemy", "Enemy"), 100, session=self.s)
                self.s.send.assert_called_once()
                self.assertIn(fragment, self.s.send.call_args.args[0])
                self.assertIn("Enemy", self.s.send.call_args.args[0])
                self.s.send.reset_mock()
                with patch.object(ninja_arts.random, "randint", return_value=100):
                    ninja_arts.weapon_hit(self.p, Player("Enemy", "Enemy"), 100, session=self.s)
                if element == "earth":
                    self.s.send.assert_called_once()
                else:
                    self.s.send.assert_not_called()

    def test_unmatched_element_and_zero_damage_produce_no_message(self):
        self.enchant("fire")
        self.s.send.reset_mock()
        target = Player("Enemy", "Enemy")
        with patch.object(ninja_arts.random, "randint", return_value=1):
            self.p.chakra_nature = "water"
            ninja_arts.weapon_hit(self.p, target, 100, session=self.s)
            self.p.chakra_nature = "fire"
            ninja_arts.weapon_hit(self.p, target, 0, session=self.s)
        self.s.send.assert_not_called()
        self.assertFalse(target.active_status_effects)

    def test_traditional_enchantments_report_actual_effects(self):
        target = Player("Enemy", "Enemy")
        for prop, fragment in (
            ("flaming", "burns"), ("frost", "Frost"), ("shocking", "stuns"),
            ("poison", "sickens"), ("sharp", "cuts"), ("vorpal", "cuts"),
        ):
            with self.subTest(prop=prop):
                self.p.equipment["wielded"] = f"A Forged Chakra Steel Sword [art:{prop}]"
                self.s.send.reset_mock()
                with patch.object(ninja_arts.random, "randint", return_value=1):
                    ninja_arts.weapon_hit(self.p, target, 100, session=self.s)
                self.s.send.assert_called_once()
                self.assertIn(fragment, self.s.send.call_args.args[0])
        self.p.equipment["wielded"] = "A Forged Chakra Steel Sword [art:life]"
        self.p.health = max(1, self.p.maximum_health - 10)
        self.s.send.reset_mock()
        ninja_arts.weapon_hit(self.p, target, 100, session=self.s)
        self.assertIn("drains", self.s.send.call_args.args[0])
        self.p.health = self.p.maximum_health
        self.s.send.reset_mock()
        ninja_arts.weapon_hit(self.p, target, 100, session=self.s)
        self.s.send.assert_not_called()

    def test_invalid_nature_and_weapon_are_rejected_without_cost(self):
        before = (self.p.chakra, self.p.stamina)
        self.enchant("water")
        self.assertEqual((self.p.chakra, self.p.stamina), before)
        self.assertEqual(self.p.equipment["wielded"], "A Forged Chakra Steel Sword")
        self.p.inventory = ["A Basic Kunai"]
        ninja_arts.use_weapon_art(self.s, "weapon enchantment", ["kunai", "fire"])
        self.assertEqual(self.p.inventory, ["A Basic Kunai"])
        self.assertEqual((self.p.chakra, self.p.stamina), before)

    def test_second_and_third_personal_natures_and_disenchant(self):
        self.p.chakra_nature_secondary = "water"
        self.p.chakra_nature_secondary_revealed = True
        item = self.enchant("water")
        self.assertEqual(ninja_arts.element_of(item), "water")
        self.p.cooldowns.clear()
        ninja_arts.use_weapon_art(self.s, "disenchantment", ["sword"])
        self.assertEqual(self.p.equipment["wielded"], "A Forged Chakra Steel Sword")
        self.p.chakra_nature_tertiary = "earth"
        self.p.chakra_nature_tertiary_revealed = True
        self.p.cooldowns.clear()
        self.assertEqual(ninja_arts.element_of(self.enchant("earth")), "earth")

    def test_bound_element_persists_in_character_save_and_trade(self):
        tagged = self.enchant("fire")
        loaded = Player.from_dict(json.loads(json.dumps(self.p.to_dict())))
        self.assertEqual(loaded.equipment["wielded"], tagged)
        loaded.inventory.append(loaded.equipment.pop("wielded"))
        traded = Player.from_dict(json.loads(json.dumps(loaded.to_dict())))
        self.assertEqual(traded.inventory[-1], tagged)
        self.assertEqual(ninja_arts.element_of(traded.inventory[-1]), "fire")


if __name__ == "__main__":
    unittest.main()
