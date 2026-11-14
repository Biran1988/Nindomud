"""Crafted Chakra Aura aliases and endgame-only gathering drops."""
import unittest
from unittest.mock import patch

import commands
import content
import data_crafting
import fishing
import gathering_job
import gems
import lumberjack
import mining
import olc
from models import Player
from session import Session, State


class AuraCraftingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def test_aura_aliases_generate_canonical_wear_slot(self):
        for case_number, selector in enumerate((["aura"], ["ca"], ["chakra", "aura"], ["chakra_aura"])):
            with self.subTest(selector=selector):
                output = []
                session = Session(output.append, lambda: None)
                session.state = State.PLAYING
                session.player = Player("AuraForger", "AuraForger", primary_class="bukijutsu", level=120)
                session.player.stamina = 500
                session.player.inventory = ["An Iron Ingot", "An Iron Ingot"]
                session.is_busy = lambda: False
                session.start_timed_action = lambda _action, _delay, done: done()
                session.enter_single_line = lambda _prompt, callback: callback("iron")
                name = f"Unique Aura {case_number} " + "_".join(selector)
                with patch.object(commands.world_autosave, "mark_dirty") if hasattr(commands, 'world_autosave') else patch('world_autosave.mark_dirty'):
                    commands.cmd_craft(session, ["armor", *selector, name])
                import crafted_identity
                matches = [i for i in session.player.inventory if crafted_identity.display(i) == name]
                self.assertEqual(len(matches), 1)
                self.assertIsNotNone(crafted_identity.vnum(matches[0]))
                proto = next(p for p in olc.OBJECT_TEMPLATES.values() if p.get("short_desc") == name)
                self.assertEqual(proto["wear_loc"], "chakra aura")
                self.assertEqual(proto["item_type"], "armor")


class TopTierGatheringTests(unittest.TestCase):
    def choices_for(self, callback, tool_name, job_level=100):
        candidates = []
        def pick(items, weights, k):
            candidates.extend((name, w) for (name, w, _xp) in items)
            return [items[-1]]
        with patch.object(gathering_job.random, "randint", return_value=100), \
             patch.object(gathering_job.random, "choices", side_effect=pick):
            found = callback(job_level, tool_name)
        self.assertFalse(found["failed"])
        return dict(candidates)

    def test_top_pickaxe_favors_chakra_and_rare_gems(self):
        weights = self.choices_for(mining.attempt_mine, "a chakra steel heartwood pickaxe")
        self.assertLess(weights["an iron ore"], weights["a steel ore"])
        self.assertGreater(weights["a chakra steel ore"], 8 * weights["a steel ore"])
        self.assertEqual(mining.gem_chance_for_tool("a chakra steel heartwood pickaxe"), 20)
        self.assertEqual(mining.gem_chance_for_tool("a copper pickaxe"), 3)
        with patch.object(gems.random, "randint", return_value=19), \
             patch.object(gems.random, "choices", return_value=[gems.GEM_TABLE[0]]):
            self.assertIsNone(gems.roll_bonus_gem(3))
            self.assertIsNotNone(gems.roll_bonus_gem(20))

    def test_top_rod_catches_only_koi_and_leviathan(self):
        expected = {"a koi", "a leviathan"}
        self.assertEqual(set(self.choices_for(fishing.attempt_catch, "a chakra steel heartwood fishing rod")), expected)
        self.assertEqual(set(self.choices_for(fishing.attempt_catch, "a chakra steel heartwood fishing rod", 75)), {"a koi"})
        self.assertIn("a minnow", self.choices_for(fishing.attempt_catch, "a kindling fishing rod"))

    def test_top_axe_never_drops_starter_wood(self):
        expected = {"an elder oak log", "an ancient heartwood log", "a yew log"}
        self.assertEqual(set(self.choices_for(lumberjack.attempt_chop, "a chakra steel heartwood axe")), expected)
        self.assertEqual(set(self.choices_for(lumberjack.attempt_chop, "a chakra steel heartwood axe", 75)), {"an elder oak log"})
        self.assertIn("a bundle of kindling", self.choices_for(lumberjack.attempt_chop, "a copper axe"))


if __name__ == "__main__":
    unittest.main()
