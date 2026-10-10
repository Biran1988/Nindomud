"""Jutsu base damage follows the existing colored damage-word scale."""

import unittest

import combat
import damage_messages
import data_jutsu
import help_system
from models import Player


class JutsuDamageLadderTests(unittest.TestCase):
    def test_every_damage_range_tracks_its_unlock_level(self):
        tiers = damage_messages.DAMAGE_TIERS
        for key, jutsu in data_jutsu.JUTSU.items():
            if jutsu["damage"] is None:
                continue
            with self.subTest(jutsu=key):
                level = min(100, max(1, jutsu["level_requirement"]))
                index = 1 + ((level - 1) * (len(tiers) - 2) + 49) // 99
                low, high = jutsu["damage"]
                strikes = 7 if jutsu.get("jutsu_type") == "sevenfold" else 1
                self.assertLessEqual(tiers[index - 1][0] + 1, low * strikes)
                self.assertLessEqual(low, high)
                self.assertLessEqual(high * strikes, tiers[index][0] or 11000)

    def test_level_75_and_special_casts(self):
        self.assertEqual(damage_messages.damage_tier(data_jutsu.JUTSU["maximum chidori"]["damage"][0])[0],
                         "CATASTROPHIC")
        self.assertEqual(damage_messages.damage_tier(data_jutsu.JUTSU["shadow shuriken technique"]["damage"][0])[0],
                         "GLANCING")
        self.assertEqual(damage_messages.damage_tier(data_jutsu.JUTSU["particle spear"]["damage"][0])[0],
                         "EXTINCTION-LEVEL")
        blast = data_jutsu.JUTSU["explosive tag kunai"]
        self.assertGreater(blast["explosive_damage"][0], blast["damage"][1])
        seven = data_jutsu.JUTSU["nanairo no rasengan"]
        self.assertLess(seven["damage"][1], data_jutsu.JUTSU["particle spear"]["damage"][0])
        caster = Player("Caster", "Caster", level=100)
        from unittest.mock import patch
        with patch.object(combat.random, "randint", side_effect=lambda a, b: a):
            total, landed, _effects = combat._sevenfold_damage(seven, caster)
        self.assertEqual(len(landed), 7)
        self.assertGreaterEqual(total, 10000)

    def test_help_uses_scaled_values(self):
        for topic, key in (("ice prison", "ice prison"),
                           ("dynamic entry", "dynamic entry"),
                           ("demonic illusion", "demonic illusion hell viewing technique")):
            jutsu = data_jutsu.JUTSU[key]
            page = next(e for e in help_system.DEFAULT_HELP_ENTRIES
                        if e["primary_keyword"] == topic)
            self.assertIn(f"{jutsu['damage'][0]}-{jutsu['damage'][1]}", page["body"])
        blast = data_jutsu.JUTSU["explosive tag kunai"]
        page = next(e for e in help_system.DEFAULT_HELP_ENTRIES
                    if e["primary_keyword"] == "explosive tag kunai")
        self.assertIn(f"{blast['explosive_damage'][0]}-{blast['explosive_damage'][1]}", page["body"])


if __name__ == "__main__":
    unittest.main()
