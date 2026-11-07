"""Apartment resale and redit flag regression checks."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import apartments
import combat
import commands
import olc
import session
import spawn_points
import storage
import world
import world_autosave
from models import Player


class ApartmentTests(unittest.TestCase):
    def setUp(self):
        self.owner = Player("Owner", "leaf", room_vnum=100)
        self.owner.apartment_room_vnum = 100
        self.owner.ryo = 5_000_000
        self.base = world.Room(100, "Owner's Apartment", "Owner's description")
        self.base.apartment = True
        self.base.owner = self.owner.name
        self.other = world.Room(300, "Another room", "Unrelated")
        self.rooms = {100: self.base, 300: self.other}
        self.s = NS(player=self.owner,
                    account=NS(name="Owner", staff_level="implementor"),
                    send=Mock())
        for p in [
            patch.object(world.WORLD, "rooms", self.rooms),
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(storage, "save_player"),
            patch.object(world_autosave, "mark_dirty"),
            patch.object(spawn_points, "remove_all_spawn_points", return_value=0),
            patch.object(session, "ACTIVE_SESSIONS", [self.s]),
            patch.object(olc, "_log"),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def build_old_room(self, typ, direction, parent=100, cost=200000):
        vnum = apartments.expansion_room_vnum(100, typ)
        room = world.Room(vnum, f"Owner's {typ}", "A built room")
        room.apartment = True
        room.owner = self.owner.name
        apartments.setup_expansion_room(room, typ)
        world.WORLD.add_room(room)
        world.WORLD.link(parent, direction, vnum)
        self.owner.apartment_expansions[typ] = {
            "direction": direction, "parent_vnum": parent, "cost": cost,
        }
        return room

    def test_hallways_unavailable_but_old_vnums_stable(self):
        self.assertNotIn("hallway", apartments.APARTMENT_ROOM_TYPES)
        self.assertEqual(apartments.expansion_room_vnum(100, "hallway"), 1000)
        self.assertEqual(apartments.expansion_room_vnum(100, "bedroom"), 1001)
        commands.cmd_buy(self.s, ["room", "hallway", "north"])
        self.assertNotIn(1000, self.rooms)

    def test_only_main_room_can_create_new_expansion(self):
        commands.cmd_buy(self.s, ["room", "bedroom", "north"])
        self.assertIn(1001, self.rooms)
        self.assertEqual(self.owner.apartment_expansions["bedroom"]["parent_vnum"], 100)
        self.owner.room_vnum = 1001
        commands.cmd_buy(self.s, ["room", "kitchen", "east"])
        self.assertNotIn(1002, self.rooms)
        self.assertIn("main apartment", self.s.send.call_args.args[0])

    def test_selling_a_room_frees_vnum_exits_and_door_flags(self):
        self.build_old_room("bedroom", "north")
        self.base.exit_flags["north"] = ["door"]
        self.base.exit_door_open["north"] = False
        self.owner.room_vnum = 1001
        commands.cmd_sell(self.s, ["room", "bedroom"])
        self.assertNotIn(1001, self.rooms)
        self.assertNotIn("north", self.base.exits)
        self.assertNotIn("north", self.base.exit_flags)
        self.assertNotIn("north", self.base.exit_door_open)
        self.assertEqual(self.owner.room_vnum, 100)

    def test_legacy_room_with_children_must_be_sold_last(self):
        self.build_old_room("hallway", "north")
        self.build_old_room("bedroom", "east", parent=1000)
        commands.cmd_sell(self.s, ["room", "hallway"])
        self.assertIn(1000, self.rooms)
        commands.cmd_sell(self.s, ["room", "bedroom"])
        commands.cmd_sell(self.s, ["room", "hallway"])
        self.assertNotIn(1000, self.rooms)
        self.assertNotIn(1001, self.rooms)

    def test_apartment_sale_removes_all_expansions_but_not_main_shell(self):
        self.build_old_room("hallway", "north")
        self.build_old_room("bedroom", "east", parent=1000)
        self.build_old_room("storage", "south")
        self.other.exits["west"] = 1001
        self.other.exit_flags["west"] = ["door"]
        self.owner.room_vnum = 1001
        commands.cmd_sell(self.s, ["apartment"])
        self.assertEqual(set(self.rooms), {100, 300})
        self.assertEqual(self.base.name, "Empty apartment")
        self.assertEqual(self.base.description, apartments.VACANT_APARTMENT_DESCRIPTION)
        self.assertIsNone(self.base.owner)
        self.assertTrue(self.base.apartment)
        self.assertEqual(self.owner.room_vnum, 100)
        self.assertIsNone(self.owner.apartment_room_vnum)
        self.assertEqual(self.owner.apartment_expansions, {})
        self.assertNotIn("west", self.other.exits)
        self.assertNotIn("west", self.other.exit_flags)

    def test_redit_flags_apartment_toggles_real_property(self):
        self.owner.room_vnum = 300
        olc.cmd_rset(self.s, ["flags", "apartment"])
        self.assertTrue(self.other.apartment)
        self.assertIn("apartment", self.other.flags)
        olc.cmd_rset(self.s, ["flags", "apartment"])
        self.assertFalse(self.other.apartment)
        self.assertNotIn("apartment", self.other.flags)
        self.owner.room_vnum = 100
        olc.cmd_rset(self.s, ["flags", "apartment"])
        self.assertTrue(self.base.apartment)  # Cannot disable an occupied apartment


if __name__ == "__main__":
    unittest.main()
