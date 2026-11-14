"""Housing VNUM reservation and reboot-safe storage-to-base door links."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import apartments
import areas
import commands
import storage
import world
from models import Player


class ApartmentAreaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.patch_data = patch.object(storage, "DATA_DIR", str(self.data))
        self.patch_data.start()
        self.addCleanup(self.patch_data.stop)
        self.rooms = {100: world.Room(100, "Kinto's Apartment", "Home")}
        self.rooms[100].apartment = True
        self.rooms[100].owner = "Kinto"
        self.patch_rooms = patch.object(world.WORLD, "rooms", self.rooms)
        self.patch_rooms.start()
        self.addCleanup(self.patch_rooms.stop)
        self.player = Player("Kinto", "Kinto", apartment_room_vnum=100, room_vnum=100)

    def test_area_is_registered_at_exact_requested_range(self):
        apartments.ensure_expansion_area()
        area = areas.find_area("apartment")
        self.assertEqual((area.vnum_start, area.vnum_end), (32001, 32500))
        self.assertFalse(area.prototype)
        apartments.ensure_expansion_area()  # idempotent
        self.assertEqual(len(areas.all_areas()), 1)

    def test_existing_builder_prototype_area_is_not_modified(self):
        areas.register_area("apartment", 32001, 32500, "Kinto")
        before = areas.find_area("apartment")
        self.assertTrue(before.prototype)
        apartments.ensure_expansion_area()
        self.assertEqual(areas.find_area("apartment"), before)

    def test_allocates_free_vnum_skipping_active_snapshot_and_saved_deed(self):
        self.rooms[32001] = world.Room(32001, "Builder room", "Preserve me")
        storage.save_world_state({"rooms": {"32002": {"vnum": 32002}}})
        other = Player("Other", "Other", apartment_room_vnum=101)
        other.apartment_expansions["storage"] = {"direction": "south", "vnum": 32003,
                                               "parent_vnum": 101, "cost": 200000}
        with patch.object(storage, "all_players", return_value=[other]):
            self.assertEqual(apartments.allocate_expansion_vnum(self.player), 32004)
        self.assertEqual(self.rooms[32001].name, "Builder room")

    def test_existing_legacy_storage_return_exit_is_restored_without_renumbering(self):
        legacy_vnum = apartments.expansion_room_vnum(100, "storage")
        self.assertEqual(legacy_vnum, 1004)
        storage_room = world.Room(legacy_vnum, "Kinto's Custom Storage", "Decorated")
        storage_room.apartment = True
        storage_room.owner = "Kinto"
        storage_room.apartment_room_type = "storage"
        storage_room.exits.clear()  # the exact reported missing return exit
        self.rooms[100].exits["north"] = legacy_vnum  # front exit survived
        self.rooms[legacy_vnum] = storage_room
        self.player.apartment_expansions = {
            "storage": {"direction": "north", "parent_vnum": 100, "cost": 200000}}
        self.player.storage_room_items = ["Stored scroll"]
        with patch.object(storage, "all_players", return_value=[self.player]), \
                patch.object(storage, "load_world_state", return_value={}):
            world.reconcile_apartment_ownership()
        self.assertIs(self.rooms[legacy_vnum], storage_room)
        self.assertEqual(storage_room.exits["south"], 100)
        self.assertEqual(self.rooms[100].exits["north"], legacy_vnum)
        self.assertEqual(storage_room.description, "Decorated")
        self.assertIs(storage_room.ground_items, self.player.storage_room_items)
        self.assertEqual(storage_room.ground_items, ["Stored scroll"])

    def test_explicit_new_storage_room_vnum_repaired_on_reboot(self):
        self.player.apartment_expansions["storage"] = {
            "direction": "west", "parent_vnum": 100, "vnum": 32025, "cost": 200000}
        self.player.storage_room_items = ["Old heirloom"]
        self.rooms[100].exits["west"] = 32025
        old = world.Room(32025, "Custom Extension", "Saved custom description")
        old.apartment = True
        old.owner = "Kinto"
        old.apartment_room_type = "storage"
        self.rooms[32025] = old
        with patch.object(storage, "all_players", return_value=[self.player]), \
                patch.object(storage, "load_world_state", return_value={}):
            world.reconcile_apartment_ownership()
        self.assertIs(self.rooms[32025], old)
        self.assertEqual(self.rooms[32025].exits["east"], 100)
        self.assertEqual(old.description, "Saved custom description")
        self.assertEqual(self.rooms[100].exits["west"], 32025)
        self.assertEqual(apartments.expansion_room_vnum(100, "storage", self.player), 32025)
        saved = Player.from_dict(self.player.to_dict())
        self.assertEqual(apartments.expansion_room_vnum(100, "storage", saved), 32025)

    def test_conflicting_builder_exit_is_never_overwritten(self):
        room = world.Room(32028, "Kinto's Storage", "")
        room.apartment = True
        room.owner = "Kinto"
        room.apartment_room_type = "storage"
        room.exits["east"] = 7654
        self.rooms[32028] = room
        self.rooms[100].exits["west"] = 32028
        self.player.apartment_expansions["storage"] = {
            "direction": "west", "parent_vnum": 100, "vnum": 32028, "cost": 200000}
        with patch.object(storage, "all_players", return_value=[self.player]), \
                patch.object(storage, "load_world_state", return_value={}):
            world.reconcile_apartment_ownership()
        self.assertEqual(room.exits["east"], 7654)
        self.assertEqual(self.rooms[100].exits["west"], 32028)

    def test_sell_new_room_uses_actual_allocated_vnum(self):
        from unittest.mock import Mock
        from types import SimpleNamespace
        self.player.ryo = 1_000_000
        session = SimpleNamespace(player=self.player, send=Mock(),
                                  account=SimpleNamespace(name="Kinto", staff_level="player"))
        with patch.object(storage, "all_players", return_value=[]), \
                patch.object(storage, "save_player"), \
                patch("world_autosave.mark_dirty"):
            commands.cmd_buy(session, ["room", "storage", "south"])
            self.assertIn(32001, self.rooms)
            self.assertEqual(self.player.apartment_expansions["storage"]["vnum"], 32001)
            self.assertEqual(self.rooms[32001].exits["north"], 100)
            commands.cmd_sell(session, ["room", "storage"])
        self.assertNotIn(32001, self.rooms)
        self.assertNotIn("south", self.rooms[100].exits)
        self.assertNotIn("storage", self.player.apartment_expansions)


if __name__ == '__main__':
    unittest.main()
