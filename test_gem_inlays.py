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

    def test_legacy_diamond_weapon_and_armor_double_remaining_durability(self):
        import equipment_durability
        self.assertEqual(gem_inlays.strength("diamond"), 0)
        name, proto = self._forged("diamond")
        player = models.Player("GemFighter", "GemFighter")
        player.equipment["wielded"] = name
        proto["durability"] = 900
        proto["max_durability"] = 5000  # old pre-diamond durable gear
        self.assertEqual(equipment_durability.state(proto), (1800, 10000))
        self.assertEqual(commands.equipped_weapon_hitroll_bonus(player), 2)
        self.assertEqual(commands.equipped_weapon_damroll_bonus(player), 2)
        self.assertEqual(commands.equipped_armor_class_bonus(player), 0)
        self.assertEqual(gem_inlays.elemental_jutsu_multiplier(player, "fire"), 1.0)
        self.assertEqual(gem_inlays.reduce_counter_damage(player, "water", 100), 100)
        proto.update(item_type="armor", wear_loc="body")
        player.equipment["wielded"] = ""
        player.equipment["body"] = name
        self.assertEqual(equipment_durability.state(proto), (1800, 10000))
        self.assertEqual(commands.equipped_armor_class_bonus(player), 0)

    def test_multiple_diamonds_grant_no_stats_or_elemental_bonuses(self):
        from copy import deepcopy
        base_name, proto = self._forged("diamond")
        player = models.Player("GemStack", "GemStack")
        player.equipment["wielded"] = base_name
        for i, slot in enumerate(("body", "head", "hands", "feet"), start=1):
            other = deepcopy(proto)
            other["short_desc"] = f"Unique Diamond {i}"
            other["wear_loc"] = slot
            vnum = 875333 + i
            olc.OBJECT_TEMPLATES[vnum] = other
            self.addCleanup(olc.OBJECT_TEMPLATES.pop, vnum, None)
            player.equipment[slot] = other["short_desc"]
        self.assertEqual(gem_inlays.equipment_flat_bonus(player), 0)
        self.assertEqual(gem_inlays.elemental_jutsu_multiplier(player, "fire"), 1.0)
        self.assertEqual(commands.equipped_weapon_hitroll_bonus(player), 10)

    def test_generated_help_explains_diamond_durability(self):
        import help_system
        by_key = {entry["primary_keyword"]: entry["body"]
                  for entry in help_system.DEFAULT_HELP_ENTRIES}
        self.assertIn("doubling remaining and maximum", by_key["inlay"])
        self.assertIn("doubles remaining and maximum", by_key["craft"])

    def test_diamond_inlay_on_individual_tool_preserves_wear_and_saved_marker(self):
        import tool_durability
        player = models.Player("GemTool", "GemTool", stamina=100)
        player.job_levels["gemcutter"] = 80
        player.equipment["tool"] = "A Copper Chisel"
        worn = "A Copper Pickaxe [125/250 uses]"
        player.inventory[:] = [worn, "A Copper Pickaxe", "A Cut Diamond"]
        messages = []
        session = SimpleNamespace(player=player, send=messages.append,
                                  is_busy=lambda: False, pending=None)
        session.start_timed_action = lambda _kind, _delay, finish: setattr(session, "pending", finish)
        with patch.object(storage, "save_player"), patch("world_autosave.mark_dirty"):
            commands.cmd_inlay(session, ["pickaxe", "with", "diamond"])
            self.assertIsNotNone(session.pending)
            session.pending()
        enhanced = player.inventory[0]
        self.assertEqual(enhanced, "A Copper Pickaxe [diamond] [250/500 uses]")
        self.assertTrue(tool_durability.has_diamond(enhanced))
        self.assertEqual(tool_durability.base_name(enhanced), "A Copper Pickaxe")
        self.assertEqual(tool_durability.display_name(enhanced), "A Copper Pickaxe")
        self.assertEqual(tool_durability.uses_left(enhanced), (250, 500))
        self.assertEqual(tool_durability.spend_use(enhanced),
                         "A Copper Pickaxe [diamond] [249/500 uses]")
        self.assertEqual(player.inventory[1], "A Copper Pickaxe")  # ordinary pick unaffected
        self.assertNotIn("A Cut Diamond", player.inventory)
        self.assertTrue(player.equipment["tool"].startswith("A Copper Chisel [249/250 uses]"))
        loaded = models.Player.from_dict(player.to_dict())
        self.assertEqual(loaded.inventory[0], enhanced)
        self.assertTrue(any("doubled" in m for m in messages))

    def test_only_diamond_can_enhance_a_tool_and_cannot_stack(self):
        import tool_durability
        player = models.Player("GemTool", "GemTool", stamina=100)
        player.job_levels["gemcutter"] = 80
        player.equipment["tool"] = "A Copper Chisel"
        player.inventory = ["A Copper Axe", "A Cut Ruby", "A Cut Diamond"]
        messages = []
        session = SimpleNamespace(player=player, send=messages.append,
                                  is_busy=lambda: False, pending=None)
        session.start_timed_action = lambda _kind, _delay, finish: setattr(session, "pending", finish)
        commands.cmd_inlay(session, ["axe", "with", "ruby"])
        self.assertIn("only", messages[-1].lower())
        self.assertEqual(player.inventory[0], "A Copper Axe")
        with patch.object(storage, "save_player"), patch("world_autosave.mark_dirty"):
            commands.cmd_inlay(session, ["axe", "with", "diamond"])
            session.pending()
        self.assertTrue(tool_durability.has_diamond(player.inventory[0]))
        player.inventory.append("A Cut Diamond")
        messages.clear()
        commands.cmd_inlay(session, ["axe", "with", "diamond"])
        self.assertIn("already", messages[-1].lower())
        self.assertEqual(tool_durability.uses_left(player.inventory[0]), (500, 500))

    def test_new_diamond_forge_initialises_double_maximum(self):
        import equipment_durability
        proto = dict(olc.DEFAULT_OBJECT_FIELDS)
        proto.update(item_type="weapon", craft_materials=["iron ingot", "iron ingot"],
                     gem_inlay="diamond")
        equipment_durability.initialise(proto)
        self.assertEqual(equipment_durability.state(proto), (5000, 5000))
        proto.update(item_type="armor", craft_materials=["chakra steel ingot"] * 2)
        equipment_durability.initialise(proto)
        self.assertEqual(equipment_durability.state(proto), (20000, 20000))
        proto["gem_inlay"] = "ruby"
        equipment_durability.initialise(proto)
        self.assertEqual(equipment_durability.state(proto), (10000, 10000))

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
