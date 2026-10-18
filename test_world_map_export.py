"""Full-world map exports are descriptive snapshots, not live-world imports."""
import copy
import dataclasses
import json
import os
import unittest
from unittest.mock import patch

import area_import
import areas
import olc
import storage
import world
from test_area_import import AreaImportTests, package


class WorldMapExportTests(unittest.TestCase):
    def setUp(self):
        AreaImportTests.setUp(self)

    def write(self, payload):
        # Reuse the area import fixture's upload helper for this suite.
        return AreaImportTests.write(self, payload)

    def test_exportworld_includes_all_areas_and_cross_area_routes(self):
        area_import.import_package(area_import.validate(package()), "Biran")
        other = dataclasses.asdict(areas.Area("South Road", 21000, 21999, "Biran"))
        entries = storage.load_areas()
        entries["south road"] = other
        entries["empty reserve"] = dataclasses.asdict(
            areas.Area("Empty Reserve", 22000, 22999, "Biran"))
        storage.save_areas(entries)
        world.WORLD.add_room(world.Room(21000, "Crossroads", "Old highway."))
        world.WORLD.rooms[20001].exits["south"] = 21000
        world.WORLD.rooms[21000].exits["north"] = 20001
        before_rooms = copy.deepcopy(world.WORLD.rooms)
        before_save = storage.load_world_state()
        path, exported = area_import.export_world()

        self.assertTrue(path.endswith("data/world_exports/nindo-world.json")
                        or path.endswith("world_exports/nindo-world.json"))
        self.assertTrue(os.path.exists(path))
        self.assertEqual(exported["format"], "nindo-world-v1")
        self.assertEqual(len(exported["markers"]), 4)
        self.assertEqual({p["area"]["name"] for p in exported["areas"]},
                         {"Test Forest", "South Road"})
        self.assertEqual(exported["links"],
                         [{"from": "South Road", "to": "Test Forest"}])
        self.assertEqual(next(m for m in exported["markers"]
                              if m["name"] == "Empty Reserve")["room_count"], 0)
        self.assertEqual(next(m for m in exported["markers"]
                              if m["name"] == "Unassigned rooms (unreserved)")["room_count"], 1)
        self.assertTrue(any("empty" in warning.lower()
                            for warning in exported["warnings"]))
        self.assertEqual(world.WORLD.rooms, before_rooms)
        self.assertEqual(storage.load_world_state(), before_save)
        with open(path, encoding="utf-8") as file:
            self.assertEqual(json.load(file)["links"], exported["links"])

    def test_exportworld_command_requires_implementor(self):
        area_import.import_package(area_import.validate(package()), "Biran")
        olc.cmd_area(self.owner, ["exportworld"])
        self.assertIn("Exported the full world map", self.owner.send.call_args.args[0])
        other = copy.copy(self.owner)
        other.account = copy.copy(self.owner.account)
        other.account.staff_level = "administrator"
        other.send = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        olc.cmd_area(other, ["exportworld"])
        self.assertIn("Only an Implementor", other.send.call_args.args[0])

    def test_export_limit_refuses_huge_world_without_overwriting_game_data(self):
        area_import.import_package(area_import.validate(package()), "Biran")
        before = storage.load_world_state()
        with patch.object(area_import, "MAX_WORLD_FILE_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "25 MB"):
                area_import.export_world()
        self.assertEqual(storage.load_world_state(), before)
        self.assertFalse(os.path.isfile(os.path.join(storage.DATA_DIR,
                                                   "world_exports", "nindo-world.json")))


if __name__ == "__main__":
    unittest.main()
