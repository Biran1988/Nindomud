"""End-to-end command tests for lumber fuel and builder furnace exceptions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import commands
import content
import cooking
import lumberjack
import olc
import wood_fuel
from models import Player


class WoodFuelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def setUp(self):
        self.player = Player("FuelTester", "FuelTester", stamina=1000)
        self.player.job_levels.update(mining=100, cooking=100, lumberjack=100)
        self.player.equipment["tool"] = "A Copper Cooking Pot"
        self.out = []
        self.pending = None
        self.session = SimpleNamespace(player=self.player, send=self.out.append,
                                       is_busy=lambda: False,
                                       start_timed_action=self.schedule)

    def schedule(self, _name, _delay, callback):
        self.pending = callback

    def resolve(self):
        self.assertIsNotNone(self.pending, "expected a timed action")
        cb, self.pending = self.pending, None
        cb()

    def test_yew_high_tier_weight_is_ten_and_sale_price_is_unchanged(self):
        self.assertEqual(lumberjack.TOP_TIER_WEIGHTS["a yew log"], 10)
        self.assertEqual(dict((name, weight) for name, _lvl, weight, _xp
                              in lumberjack.weighted_find_table(3))["a yew log"], 10)
        import data_crafting
        self.assertEqual(data_crafting.MATERIALS["yew log"]["price_ryo"], 40000)

    def test_smelting_rejects_no_log_outside_furnace_without_consuming_ore(self):
        self.player.inventory = ["An Iron Ore", "A Bundle of Kindling"]
        with patch.object(commands.world.WORLD, "get", return_value=SimpleNamespace(flags=[])):
            commands.cmd_smelt(self.session, ["iron", "ore"])
        self.assertIsNone(self.pending)
        self.assertEqual(self.player.inventory, ["An Iron Ore", "A Bundle of Kindling"])
        self.assertTrue(any("one log" in msg for msg in self.out))

    def test_smelting_uses_cheapest_log_not_rare_yew(self):
        self.player.inventory = ["A Yew Log", "A Sturdy Oak Log", "An Iron Ore"]
        with patch.object(commands.world.WORLD, "get", return_value=SimpleNamespace(flags=[])):
            commands.cmd_smelt(self.session, ["iron", "ore"])
            self.resolve()
        self.assertCountEqual(self.player.inventory, ["A Yew Log", "An Iron Ingot"])
        self.assertTrue(any("burn A Sturdy Oak Log" in msg for msg in self.out))

    def test_smelting_in_builder_furnace_does_not_consume_logs(self):
        self.assertIn("furnace", olc.VALID_ROOM_FLAGS)
        self.player.inventory = ["An Iron Ore"]
        room = SimpleNamespace(flags=["furnace"])
        with patch.object(commands.world.WORLD, "get", return_value=room):
            commands.cmd_smelt(self.session, ["iron", "ore"])
            self.resolve()
        self.assertEqual(self.player.inventory, ["An Iron Ingot"])
        self.assertFalse(any("burn" in msg.lower() for msg in self.out))

    def test_disappearing_log_cancels_smelt_before_ore_consumed(self):
        self.player.inventory = ["A Sturdy Oak Log", "A Steel Ore"]
        with patch.object(commands.world.WORLD, "get", return_value=SimpleNamespace(flags=[])):
            commands.cmd_smelt(self.session, ["steel", "ore"])
            self.player.inventory.remove("A Sturdy Oak Log")
            self.resolve()
        self.assertEqual(self.player.inventory, ["A Steel Ore"])
        self.assertTrue(any("ore is not consumed" in msg for msg in self.out))

    def test_cooking_requires_wood_even_in_owned_kitchen_and_pot(self):
        self.player.inventory = ["A Minnow"]
        for room in (None, SimpleNamespace(apartment_room_type="kitchen", owner=self.player.name)):
            with self.subTest(room=room), patch.object(commands.world.WORLD, "get", return_value=room):
                commands.cmd_cook(self.session, ["minnow"])
                self.assertIsNone(self.pending)
                self.assertEqual(self.player.inventory, ["A Minnow"])
        self.assertTrue(any("wood item" in msg for msg in self.out))

    def test_burned_cooking_consumes_kindling_even_when_dish_fails(self):
        self.player.inventory = ["A Minnow", "A Bundle of Kindling"]
        with (patch.object(commands.world.WORLD, "get", return_value=None),
              patch.object(cooking, "attempt_cook", return_value={"burned": True})):
            commands.cmd_cook(self.session, ["minnow"])
            self.resolve()
        self.assertEqual(self.player.inventory, [])
        self.assertTrue(any("consumed" in msg for msg in self.out))

    def test_cooking_kitchen_requires_wood_but_not_pot(self):
        self.player.equipment.clear()
        self.player.inventory = ["A Minnow", "A Birch Branch", "A Yew Log"]
        kitchen = SimpleNamespace(apartment_room_type="kitchen", owner=self.player.name)
        with (patch.object(commands.world.WORLD, "get", return_value=kitchen),
              patch.object(cooking, "attempt_cook", return_value={"burned": False,
                                                                   "name": "A Cooked Minnow", "xp": 10}),
              patch.object(commands, "_award_job_action_xp")):
            commands.cmd_cook(self.session, ["minnow"])
            self.resolve()
        self.assertCountEqual(self.player.inventory, ["A Cooked Minnow", "A Yew Log"])
        self.assertTrue(any("A Birch Branch" in msg for msg in self.out))

    def test_cooking_missing_wood_during_delay_preserves_ingredient_and_pot(self):
        self.player.inventory = ["A Minnow", "A Bundle of Kindling"]
        with patch.object(commands.world.WORLD, "get", return_value=None):
            commands.cmd_cook(self.session, ["minnow"])
            self.player.inventory.remove("A Bundle of Kindling")
            self.resolve()
        self.assertEqual(self.player.inventory, ["A Minnow"])
        self.assertEqual(self.player.equipment["tool"], "A Copper Cooking Pot")

    def test_fuel_selector_rejects_non_wood_and_prioritizes_low_cost(self):
        self.assertEqual(wood_fuel.find_fuel(["A Yew Log", "A Birch Branch"]), "A Birch Branch")
        self.assertEqual(wood_fuel.find_fuel(["A Yew Log", "A Birch Branch"], logs_only=True), "A Yew Log")
        self.assertIsNone(wood_fuel.find_fuel(["A Basic Kunai", "An Iron Ingot"]))


if __name__ == "__main__":
    unittest.main()
