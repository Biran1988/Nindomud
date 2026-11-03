"""Regression coverage for rare mining gems and persistent elemental inlays."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import content
import commands
import elemental_counters
import gem_inlays
import gemcutter
import gems
import mining
import models
import olc
import storage


class GemInlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def test_rough_quartz_is_only_a_rare_bonus_not_primary_mining(self):
        self.assertEqual({name for name, *_ in mining.FIND_TABLE},
                         {"an iron ore", "a steel ore", "a chakra steel ore"})
        self.assertIn("a rough quartz", {name for name, *_ in gems.GEM_TABLE})
        self.assertEqual(gems.FIND_CHANCE_PERCENT, 3)

    def test_all_bonus_gems_are_cuttable_and_have_real_item_prototypes(self):
        for item_name, _rarity, _weight, _color in gems.GEM_TABLE:
            with self.subTest(gem=item_name):
                self.assertIn(item_name, gemcutter.RECIPES)
                cut_name, level, _xp = gemcutter.RECIPES[item_name]
                gem = gem_inlays.gem_from_cut_item(cut_name)
                self.assertIsNotNone(gem)
                self.assertGreaterEqual(level, 1)
                self.assertTrue(any(p["short_desc"] == cut_name
                                    for p in olc.OBJECT_TEMPLATES.values()))

    def test_five_elemental_gems_are_equal_power_rarity_and_cutting_level(self):
        by_gem = {name.split()[-1]: (rarity, weight)
                  for name, rarity, weight, _ in gems.GEM_TABLE}
        for key, element in gem_inlays.ELEMENT_GEMS.items():
            with self.subTest(gem=key, element=element):
                self.assertEqual(by_gem[key], ("epic", 5))
                self.assertEqual(gemcutter.RECIPES["an " + key if key in ("amethyst", "emerald") else "a " + key][1], 60)
                self.assertEqual(gem_inlays.strength(key), 10)
                self.assertIn(element, elemental_counters.ELEMENT_COUNTERS)

    def _forged(self, gem):
        forged_name = "A Unique Gem Inlay Test Weapon"
        vnum = 875333
        proto = dict(olc.DEFAULT_OBJECT_FIELDS)
        proto.update(short_desc=forged_name, item_type="weapon",
                     weapon_type="sword", wear_loc="wielded",
                     craft_materials=["steel ingot", "steel ingot"],
                     stat_bonuses={"hitroll": 2, "damroll": 2},
                     gem_inlay=gem)
        olc.OBJECT_TEMPLATES[vnum] = proto
        self.addCleanup(olc.OBJECT_TEMPLATES.pop, vnum, None)
        return forged_name, proto

    def test_elemental_inlay_adds_ten_stats_and_resists_own_counter(self):
        for gem, element in gem_inlays.ELEMENT_GEMS.items():
            with self.subTest(gem=gem):
                name, proto = self._forged(gem)
                player = models.Player("GemFighter", "GemFighter")
                player.equipment["wielded"] = name
                self.assertEqual(gem_inlays.equipment_flat_bonus(player), 10)
                self.assertEqual(commands.equipped_weapon_hitroll_bonus(player), 12)
                self.assertEqual(commands.equipped_weapon_damroll_bonus(player), 12)
                self.assertEqual(proto["stat_bonuses"], {"hitroll": 2, "damroll": 2})
                self.assertEqual(proto["short_desc"], name)
                self.assertEqual(gem_inlays.elemental_jutsu_multiplier(player, element), 1.15)
                self.assertEqual(gem_inlays.elemental_jutsu_multiplier(player, "none"), 1.0)
                counter = elemental_counters.counters(element)
                self.assertEqual(gem_inlays.reduce_counter_damage(player, counter, 100), 85)
                self.assertEqual(gem_inlays.reduce_counter_damage(player, element, 100), 100)
                olc.OBJECT_TEMPLATES.pop(875333, None)

    def test_forged_inlay_works_after_weapon_elemental_enchantment(self):
        name, _ = self._forged("ruby")
        player = models.Player("GemFighter", "GemFighter")
        player.equipment["wielded"] = name + " [element:fire]"
        self.assertEqual(gem_inlays.equipment_flat_bonus(player), 10)

    def test_inlay_command_consumes_one_cut_gem_without_renaming_item(self):
        name, proto = self._forged("")
        player = models.Player("GemFighter", "GemFighter", stamina=100)
        player.inventory[:] = [name, "A Cut Quartz"]
        player.equipment["tool"] = "A Copper Chisel"
        player.job_levels["gemcutter"] = 1
        messages = []
        session = SimpleNamespace(player=player, send=messages.append,
                                  is_busy=lambda: False, pending=None)
        session.start_timed_action = lambda _kind, _delay, finish: setattr(session, "pending", finish)
        with patch.object(storage, "save_player"):
            commands.cmd_inlay(session, ["weapon", "with", "quartz"])
            self.assertIsNotNone(session.pending)
            session.pending()
        self.assertEqual(proto["gem_inlay"], "quartz")
        self.assertEqual(player.inventory, [name])
        self.assertEqual(gem_inlays.strength(proto["gem_inlay"]), 2)
        self.assertTrue(player.equipment["tool"].startswith("A Copper Chisel [249/250 uses]"))
        self.assertFalse(any("[inlay:" in s.lower() for s in player.inventory))


if __name__ == "__main__":
    unittest.main()
