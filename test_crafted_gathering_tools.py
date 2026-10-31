"""Four-tier rods, axes and pickaxes: recipes, overlap, cap, equip and save."""
import unittest
from unittest.mock import patch

import commands
import content
import data_crafting
import fishing
import gathering_job
import lumberjack
import mining
import models
import olc
import tool_durability
from session import Session, State


class CraftedGatheringToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def make_session(self, ninja_class="bukijutsu", level=100):
        output = []
        session = Session(output.append, lambda: None)
        session.state = State.PLAYING
        p = models.Player("ToolsmithTest", "ToolsmithTest", primary_class=ninja_class, level=level)
        p.stamina = 500
        session.player = p
        session.is_busy = lambda: False
        session.start_timed_action = lambda name, delay, callback: callback()
        return session, p, output

    def test_all_nine_recipes_and_forge_durability(self):
        for kind, table in (("rod", fishing.RODS), ("axe", lumberjack.AXES),
                            ("pickaxe", mining.PICKAXES)):
            for tier, recipe in data_crafting.TOOL_RECIPES.items():
                with self.subTest(kind=kind, tier=tier):
                    sess, p, out = self.make_session()
                    p.inventory.extend([recipe["wood"], recipe["ingot"]])
                    with patch.object(commands.storage, "save_player") as saved:
                        commands.cmd_craft(sess, ["tool", kind, tier])
                    name = data_crafting.job_tool_name(kind, tier)
                    self.assertIn(name, p.inventory)
                    self.assertNotIn(recipe["wood"], p.inventory)
                    self.assertNotIn(recipe["ingot"], p.inventory)
                    self.assertIn(name.lower(), table)
                    self.assertEqual(tool_durability.uses_left(name), (recipe["uses"], recipe["uses"]))
                    self.assertEqual(commands._item_wear_loc(name), "tool")
                    saved.assert_called_once_with(p)
                    restored = models.Player.from_dict(p.to_dict())
                    self.assertIn(name, restored.inventory)
                    self.assertEqual(olc.OBJECT_TEMPLATES[next(i for i,v in olc.OBJECT_TEMPLATES.items() if v.get("short_desc")==name)]["item_type"], "tool")

    def test_only_bukijutsu_blacksmith_25_or_higher(self):
        recipe = data_crafting.TOOL_RECIPES["iron"]
        for ninja_class, lvl in (("ninjutsu", 100), ("bukijutsu", 24)):
            sess, p, out = self.make_session(ninja_class, lvl)
            p.inventory = [recipe["wood"], recipe["ingot"]]
            commands.cmd_craft(sess, ["tool", "rod", "iron"])
            self.assertEqual(p.inventory, [recipe["wood"], recipe["ingot"]])
            self.assertIn("Bukijutsu blacksmith", "".join(out))

    def test_requires_exact_pair_and_consumes_only_on_success(self):
        sess, p, out = self.make_session()
        p.inventory = ["A Sturdy Oak Log", "A Chakra Steel Ingot"]
        commands.cmd_craft(sess, ["rod", "iron"])
        self.assertNotIn(data_crafting.job_tool_name("rod", "iron"), p.inventory)
        self.assertEqual(len(p.inventory), 2)

    def test_all_three_jobs_overlap_and_have_production_chain(self):
        for table, find, attempt in ((fishing.RODS, fishing.FIND_TABLE, fishing.attempt_catch),
                                     (mining.PICKAXES, mining.FIND_TABLE, mining.attempt_mine),
                                     (lumberjack.AXES, lumberjack.FIND_TABLE, lumberjack.attempt_chop)):
            tiers = sorted(table.items(), key=lambda x: x[1]["tier"])
            seen = set()
            for toolname, spec in tiers:
                with self.subTest(toolname=toolname):
                    allowed = {n for n, minlevel, _, _ in find if minlevel <= spec["max_resource_level"]}
                    self.assertTrue(seen.issubset(allowed))
                    self.assertGreaterEqual(len(allowed), len(seen))
                    seen = allowed
                    captured = []
                    def choices(available, weights, k):
                        captured.extend(n for n, _, _ in available)
                        return [available[-1]]
                    with patch.object(gathering_job.random, "randint", return_value=100), \
                         patch.object(gathering_job.random, "choices", side_effect=choices):
                        result = attempt(100, toolname)
                    self.assertEqual(set(captured), allowed)
                    self.assertEqual(result["name"], find[next(i for i,x in enumerate(find) if x[0] == result["name"])][0])
        self.assertIn("an ancient heartwood log", {n for n, *_ in lumberjack.FIND_TABLE if n in seen} | {n for n,*_ in lumberjack.FIND_TABLE})
        self.assertEqual(mining.PICKAXES["a copper pickaxe"]["max_resource_level"], 1)
        self.assertEqual(mining.PICKAXES["a steel ironwood pickaxe"]["max_resource_level"], 55)
        self.assertEqual(lumberjack.AXES["a steel ironwood axe"]["max_resource_level"], 85)
        self.assertEqual(fishing.RODS["an ironbound oak fishing rod"]["max_resource_level"], 40)
        self.assertEqual(fishing.RODS["a chakra steel heartwood fishing rod"]["max_resource_level"], 90)

    def test_new_rod_tiers_species(self):
        fish = {n: level for n, level, _, _ in fishing.FIND_TABLE}
        for name, max_level in (("a kindling fishing rod", 15),
                                ("an ironbound oak fishing rod", 40),
                                ("a steel ironwood fishing rod", 75),
                                ("a chakra steel heartwood fishing rod", 90)):
            options = {n for n, level in fish.items() if level <= fishing.RODS[name]["max_resource_level"]}
            self.assertIn("a trout", options)
            if max_level >= 40:
                self.assertIn("a bass", options)
                self.assertIn("a salmon", options)
            else:
                self.assertNotIn("a bass", options)
            self.assertEqual("a leviathan" in options, max_level == 90)


if __name__ == "__main__":
    unittest.main()
