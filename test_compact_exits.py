"""Regression coverage for compact exits and room-content display order."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import combat
import world
from models import Player


class CompactRoomLookTests(unittest.TestCase):
    def setUp(self):
        room = world.Room(9301, "Test Room", "Test description.")
        room.exits.update({"south": 9302, "north": 9303, "east": 9304})
        self.room = room

    def test_exits_use_one_line_and_cardinal_order(self):
        lines = commands._format_exits(self.room)
        self.assertEqual(len(lines), 1)
        self.assertLess(lines[0].index("North"), lines[0].index("East"))
        self.assertLess(lines[0].index("East"), lines[0].index("South"))
        self.assertTrue(lines[0].startswith("&"))

    def test_hidden_exit_requires_staff(self):
        self.room.exit_flags["north"] = ["hidden"]
        self.assertNotIn("North", commands._format_exits(self.room, False)[0])
        self.assertIn("North (hidden)", commands._format_exits(self.room, True)[0])

    def test_closed_door_is_labeled(self):
        self.room.exit_flags["south"] = ["door"]
        self.assertIn("South (closed)", commands._format_exits(self.room)[0])

    def test_no_exits_or_only_hidden_exits(self):
        self.room.exits.clear()
        self.assertIn("Exits: none", commands._format_exits(self.room)[0])
        self.room.exits["south"] = 9302
        self.room.exit_flags["south"] = ["hidden"]
        self.assertIn("Exits: none", commands._format_exits(self.room)[0])

    def test_mobs_render_before_ground_items(self):
        player = Player("Viewer", "Viewer", room_vnum=9301)
        session = NS(player=player, account=NS(staff_level="player"), send=Mock())
        session.active_sessions = lambda: [session]
        mob = NS(name="A training student", template_vnum=999, invisible=False,
                 active_status_effects={}, shadow_clone_owner="")
        self.room.ground_items = ["A practice kunai"]
        with patch.object(world.WORLD, "get", return_value=self.room), \
             patch.object(combat, "mobs_in_room", return_value=[mob]), \
             patch.object(commands, "_is_invisible_mob", return_value=False), \
             patch.object(commands, "_is_invisible_item", return_value=False), \
             patch.object(commands, "_find_object_prototype_by_name", return_value=None), \
             patch.object(commands.corpses, "corpses_in_room", return_value=[]):
            commands.cmd_look(session, [])
        output = session.send.call_args.args[0]
        self.assertLess(output.index("A training student"), output.index("A practice kunai"))


if __name__ == "__main__":
    unittest.main()
