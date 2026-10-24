"""Bulk room pickup and explicitly targeted bulk selling."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import inventory
import content
import currency_piles
import olc
import storage
import world
from models import Player


class BulkItemCommandTests(unittest.TestCase):
    def setUp(self):
        self.room = world.Room(79201, "Test Market", "A market square.")
        self.player = Player("BulkTester", "BulkTester", room_vnum=self.room.vnum)
        self.player.ryo = 0
        self.session = NS(player=self.player, send=Mock(), broadcast_room=Mock())
        self.patches = [
            patch.object(world.WORLD, "rooms", {self.room.vnum: self.room}),
            patch.object(content, "SHOPS", {self.room.vnum: {"type": "food"}}),
            patch.object(commands, "_find_shopkeeper", return_value=None),
            patch.object(commands, "_has_no_take_flag",
                         side_effect=lambda name: "sign" in name.lower()),
            patch.object(olc, "OBJECT_TEMPLATES", {}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_get_all_skips_fixed_decorations_and_collects_everything_else(self):
        self.room.ground_items = ["a sardine", "a minnow", "a sign", "a sardine"]
        commands.cmd_get(self.session, ["all"])
        self.assertEqual(self.player.inventory, ["a sardine", "a minnow", "a sardine"])
        self.assertEqual(self.room.ground_items, ["a sign"])
        self.assertIn("3 item(s)", self.session.send.call_args_list[0].args[0])
        self.assertTrue(any("fixed decoration" in c.args[0]
                            for c in self.session.send.call_args_list))

    def test_get_all_only_picks_up_what_fits_and_continues_after_a_full_stack(self):
        self.player.inventory = ["a sardine"] * inventory.MAX_STACK_SIZE
        self.room.ground_items = ["a sardine", "a minnow"]
        commands.cmd_get(self.session, ["all"])
        self.assertEqual(self.player.inventory.count("a sardine"), inventory.MAX_STACK_SIZE)
        self.assertIn("a minnow", self.player.inventory)
        self.assertEqual(self.room.ground_items, ["a sardine"])

    def test_get_all_named_only_picks_matching_items(self):
        self.room.ground_items = ["a sardine", "a minnow", "a sardine"]
        self.room.ground_ryo = [20]
        commands.cmd_get(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine", "a sardine"])
        self.assertEqual(self.room.ground_items, ["a minnow"])
        self.assertEqual(self.room.ground_ryo, [20])

    def test_get_all_also_collects_ryo_without_using_inventory_slots(self):
        self.player.inventory = [f"unique-{i}" for i in range(20)]
        self.room.ground_ryo = [12, 33]
        with patch.object(storage, "save_player"), patch.object(currency_piles, "save_piles"):
            commands.cmd_get(self.session, ["all"])
        self.assertEqual(self.player.ryo, 45)
        self.assertEqual(self.room.ground_ryo, [])
        self.assertEqual(len(self.player.inventory), 20)

    def test_sell_all_sardine_leaves_every_other_item_alone(self):
        self.player.inventory = ["a sardine", "a minnow", "a sardine", "a sardine"]
        commands.cmd_sell(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a minnow"])
        self.assertEqual(self.player.ryo, 6)
        self.assertIn("3 item(s)", self.session.send.call_args.args[0])

    def test_sell_quantity_only_sells_requested_matching_copies(self):
        self.player.inventory = ["a sardine"] * 5 + ["a minnow"]
        commands.cmd_sell(self.session, ["2", "sardine"])
        self.assertEqual(self.player.inventory.count("a sardine"), 3)
        self.assertEqual(self.player.inventory.count("a minnow"), 1)
        self.assertEqual(self.player.ryo, 4)

    def test_sell_all_without_item_is_rejected_not_entire_inventory(self):
        self.player.inventory = ["a sardine", "a minnow"]
        commands.cmd_sell(self.session, ["all"])
        self.assertEqual(self.player.inventory, ["a sardine", "a minnow"])
        self.assertEqual(self.player.ryo, 0)
        self.assertIn("sell all <item>", self.session.send.call_args.args[0])

    def test_sell_all_respects_food_shop_category(self):
        self.player.inventory = ["a sardine", "a sword"]
        commands.cmd_sell(self.session, ["all", "sword"])
        self.assertEqual(self.player.inventory, ["a sardine", "a sword"])
        self.assertEqual(self.player.ryo, 0)
        self.assertIn("doesn't buy", self.session.send.call_args.args[0])

    def test_sell_all_skips_glued_items(self):
        self.player.inventory = ["a sardine", "a sardine [glued]"]
        commands.cmd_sell(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a sardine [glued]"])
        self.assertEqual(self.player.ryo, 2)

    def test_sell_all_preserves_contents_of_unsold_backpack(self):
        self.player.inventory = ["a sardine", "a satchel", "a sardine"]
        self.player.backpack_contents = {"1": ["rare seal"]}
        commands.cmd_sell(self.session, ["all", "sardine"])
        self.assertEqual(self.player.inventory, ["a satchel"])
        self.assertEqual(self.player.backpack_contents, {"0": ["rare seal"]})
        self.player.ryo = 0
        commands.cmd_sell(self.session, ["all", "satchel"])
        self.assertEqual(self.player.inventory, ["a satchel"])
        self.assertEqual(self.player.backpack_contents, {"0": ["rare seal"]})
        self.assertEqual(self.player.ryo, 0)


if __name__ == "__main__":
    unittest.main()
