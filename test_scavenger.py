"""Scavenger mobs collect loose takeable objects without persisting them."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import combat
import commands
import olc
import world


class ScavengerTests(unittest.TestCase):
    def test_flag_is_builder_settable_and_obeys_no_take(self):
        self.assertIn("Scavenger", olc.VALID_MOB_ACT_FLAGS)
        room_vnum = 987654
        template_vnum = 987654
        room = SimpleNamespace(ground_items=["Dropped Kunai", "Fixed Sign", "Dropped Kunai"],
                               apartment=False)
        mob = SimpleNamespace(template_vnum=template_vnum, health=20,
                              scavenged_items=[], room_vnum=room_vnum)
        combat.MOBS_BY_ROOM[room_vnum] = [mob]
        combat.MOB_TEMPLATES[template_vnum] = {"act_flags": ["Npc", "Scavenger"]}
        try:
            with patch.object(world.WORLD, "get", return_value=room), \
                 patch.object(commands, "_has_no_take_flag", side_effect=lambda name: name == "Fixed Sign"):
                combat.process_scavengers()
                self.assertEqual(room.ground_items, ["Fixed Sign"])
                self.assertEqual(mob.scavenged_items, ["Dropped Kunai", "Dropped Kunai"])
                room.apartment = True
                room.ground_items.append("Stored Item")
                combat.process_scavengers()
                self.assertEqual(room.ground_items, ["Fixed Sign", "Stored Item"])
        finally:
            combat.MOBS_BY_ROOM.pop(room_vnum, None)
            combat.MOB_TEMPLATES.pop(template_vnum, None)


if __name__ == "__main__":
    unittest.main()
