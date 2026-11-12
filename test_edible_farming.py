"""Regression tests for edible raw farm harvests and stronger cooked dishes."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import commands
import consumables
import cooking
import farming
import item_types
from models import Player


class EdibleFarmFoodTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("CropTester", "CropTester")
        self.player.maximum_stamina = 500
        self.player.stamina = 0
        self.messages = []
        self.session = SimpleNamespace(
            player=self.player, send=self.messages.append,
            is_busy=lambda: False,
            start_timed_action=lambda _name, _delay, resolve: resolve(),
        )

    def test_all_eight_farming_foods_have_better_cooked_versions(self):
        regular_harvests = {name for name, *_ in farming.FIND_TABLE
                            if name != "medicinal herbs"}
        self.assertEqual(set(farming.EDIBLE_CROPS), regular_harvests)
        for raw, recipe in farming.EDIBLE_CROPS.items():
            with self.subTest(crop=raw):
                self.assertGreater(recipe["cooked_stamina"], recipe["raw_stamina"])
                self.assertIn(raw, cooking.INGREDIENTS)
                self.assertEqual(cooking.INGREDIENTS[raw]["dish"], recipe["dish"])
                self.assertEqual(cooking.COOKING_XP[raw], recipe["cooking_xp"])
                self.assertEqual(item_types.classify_item(raw), "food")
                self.assertEqual(item_types.classify_item(recipe["dish"]), "food")

    def test_raw_and_cooked_farming_items_are_consumed_with_eat(self):
        for raw, recipe in farming.EDIBLE_CROPS.items():
            for item, amount in ((raw, recipe["raw_stamina"]),
                                 (recipe["dish"], recipe["cooked_stamina"])):
                with self.subTest(item=item):
                    self.player.inventory = [item]
                    self.player.stamina = 0
                    consumables.consume(self.session, "eat", item)
                    self.assertEqual(self.player.stamina, amount)
                    self.assertEqual(self.player.inventory, [])
                    self.assertTrue(any("recover" in line.lower()
                                        for line in self.messages))
                    self.messages.clear()

    def test_cook_command_uses_real_crop_recipes_and_produces_edible_food(self):
        self.player.equipment["tool"] = "A Copper Cooking Pot"
        for raw, recipe in farming.EDIBLE_CROPS.items():
            with self.subTest(crop=raw):
                self.player.inventory = [raw]
                self.player.stamina = 200
                with (patch.object(commands.world.WORLD, "get", return_value=None),
                      patch.object(commands, "_use_held_job_tool", return_value=True),
                      patch.object(commands, "_award_job_action_xp") as award,
                      patch.object(commands.jobs, "try_deduct_action_stamina", return_value=True),
                      patch.object(cooking.random, "randint", return_value=100)):
                    commands.cmd_cook(self.session, raw.split()[1:])
                self.assertEqual(self.player.inventory, [recipe["dish"]])
                award.assert_called_once_with(self.session, "cooking", recipe["cooking_xp"])
                self.assertIn(f"You cooked {raw}.", self.messages)
                self.assertFalse(any("You cook A Cooked" in line for line in self.messages))
                self.messages.clear()

    def test_herbs_remain_ingredient_and_not_an_edible_crop(self):
        self.assertNotIn("medicinal herbs", farming.EDIBLE_CROPS)
        self.assertNotIn("medicinal herbs", cooking.INGREDIENTS)
        self.assertEqual(item_types.classify_item("medicinal herbs"), "misc")
        self.player.inventory = ["medicinal herbs"]
        consumables.consume(self.session, "eat", "medicinal herbs")
        self.assertEqual(self.player.inventory, ["medicinal herbs"])
        self.assertTrue(any("can't eat" in line.lower() for line in self.messages))


if __name__ == "__main__":
    unittest.main()
