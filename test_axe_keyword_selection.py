"""Regression for lumberjack axe keywords versus mining pickaxes."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import commands
import content
from models import Player


class AxeKeywordSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def session_for(self, inventory, equipped=None):
        player = Player(name="LumberjackTester", account_name="LumberjackTester")
        player.inventory = list(inventory)
        if equipped:
            player.equipment["tool"] = equipped
        messages = []
        return SimpleNamespace(player=player, send=messages.append), messages

    def test_axe_does_not_match_pickaxe_but_pickaxe_still_matches(self):
        self.assertFalse(commands._item_matches("axe", "A Copper Pickaxe"))
        self.assertFalse(commands._item_matches("axe", "A Steel Ironwood Pickaxe [25/250 uses]"))
        self.assertTrue(commands._item_matches("axe", "A Copper Axe"))
        self.assertTrue(commands._item_matches("steel axe", "A Steel Ironwood Axe"))
        self.assertTrue(commands._item_matches("pickaxe", "A Copper Pickaxe"))
        self.assertTrue(commands._item_matches("iron pick", "An Ironbound Oak Pickaxe"))

    def test_hold_axe_selects_lumberjack_tool_even_after_pickaxe(self):
        session, messages = self.session_for(["A Copper Pickaxe", "A Copper Axe"])
        with patch.object(commands, "_fire_item_trigger"), patch("room_actions.emit"):
            commands.cmd_hold(session, ["axe"])
        self.assertEqual(session.player.equipment["tool"], "A Copper Axe")
        self.assertEqual(session.player.inventory, ["A Copper Pickaxe"])
        self.assertTrue(any("You hold" in message for message in messages))

    def test_hold_axe_replaces_equipped_pickaxe(self):
        session, messages = self.session_for(["A Copper Axe"], "A Copper Pickaxe")
        with patch.object(commands, "_fire_item_trigger"), patch("room_actions.emit"):
            commands.cmd_hold(session, ["axe"])
        self.assertEqual(session.player.equipment["tool"], "A Copper Axe")
        self.assertEqual(session.player.inventory, ["A Copper Pickaxe"])
        self.assertFalse(any("already using" in message for message in messages))

    def test_remove_axe_does_not_remove_equipped_pickaxe(self):
        session, messages = self.session_for([], "A Copper Pickaxe")
        with patch("room_actions.emit"):
            commands.cmd_remove(session, ["axe"])
        self.assertEqual(session.player.equipment["tool"], "A Copper Pickaxe")
        self.assertIn("aren't wearing", messages[-1])

    def test_indexed_axe_selection_ignores_pickaxe(self):
        items = ["A Copper Pickaxe", "A Copper Axe", "A Steel Ironwood Pickaxe", "A Steel Ironwood Axe"]
        self.assertEqual(commands.find_indexed_item("2.axe", items), "A Steel Ironwood Axe")
        self.assertEqual(commands.find_indexed_item("pickaxe", items), "A Copper Pickaxe")


if __name__ == "__main__":
    unittest.main()
