"""Medicinal Herbs are a rare Farming harvest, not a duplicate food item."""
import unittest
from unittest.mock import patch

import content
import farming
import gathering_job
import olc


class FarmingMedicinalHerbsTests(unittest.TestCase):
    def test_herbs_are_rare_and_require_farming_level_20(self):
        name, level, weight, xp = next(item for item in farming.FIND_TABLE
                                        if item[0] == "medicinal herbs")
        self.assertEqual(level, 20)
        self.assertLess(weight, 10)
        self.assertGreater(xp, 0)
        self.assertTrue(farming.can_farm_here("plains"))

    def test_harvest_pool_unlocks_herbs_only_from_level_20(self):
        captured = []
        def choose(available, weights, k):
            names = [name for name, _, _ in available]
            captured.append(names)
            return [available[-1]]
        with patch.object(gathering_job.random, "randint", return_value=100), \
                patch.object(gathering_job.random, "choices", side_effect=choose):
            low = farming.attempt_farm(19, "a copper hoe")
            high = farming.attempt_farm(20, "a copper hoe")
        self.assertNotIn("medicinal herbs", captured[0])
        self.assertIn("medicinal herbs", captured[1])
        self.assertNotEqual(low["name"], "medicinal herbs")
        self.assertEqual(high["name"], "medicinal herbs")
        self.assertEqual(high["xp"], 35)

    def test_herbs_use_existing_crafting_item_not_new_food_prototype(self):
        self.assertEqual(content._ITEM_VNUMS["medicinal_herbs"], 9809)
        templates = {}
        with patch.object(olc, "OBJECT_TEMPLATES", templates):
            content._register_shared_items()
            herb = templates[9809]
            self.assertEqual(herb["short_desc"], "Medicinal Herbs")
            self.assertEqual(herb["item_type"], "misc")
            self.assertNotIn(20314, templates)


if __name__ == "__main__":
    unittest.main()
