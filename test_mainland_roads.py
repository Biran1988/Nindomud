"""Regression checks for the one-time mainland road /data migration."""
import collections
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import areas
import mainland_roads as roads
import storage
import world


def registered_areas():
    entries = [("Mainland Road Network", roads.FIRST_VNUM, roads.LAST_VNUM)]
    entries += [(area, start, end)
                for _, area, _, _, _, start, end in roads.DESTINATIONS]
    return {name.casefold(): {"name": name, "vnum_start": start,
                              "vnum_end": end, "creator": "Biran"}
            for name, start, end in entries}


def distance(exits, begin, end):
    queue = collections.deque([(begin, 0)])
    visited = {begin}
    while queue:
        room, depth = queue.popleft()
        if room == end:
            return depth
        for neighbor in exits[room].values():
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
    return None


class RoadGeometryTests(unittest.TestCase):
    def test_exact_vnums_and_reciprocal_navigation(self):
        built, hubs = roads.build_rooms()
        self.assertEqual(hubs["leaf_gate"], 20501)
        self.assertEqual(len(built), 1528)
        self.assertEqual(set(built), set(range(20501, 22029)))
        self.assertEqual(built[20501].exits["north"], 9)
        for vnum, room in built.items():
            for direction, destination in room.exits.items():
                if destination in built:
                    self.assertEqual(
                        built[destination].exits[roads.REVERSE[direction]],
                        vnum, f"{vnum} -> {destination}")
        # No crossroads leave a through-route inside a country.
        for name, area, vnum, hub, heading, start, end in roads.DESTINATIONS:
            self.assertEqual(built[hubs[hub]].exits[heading], vnum)

    def test_all_major_villages_are_spurs_not_through_routes(self):
        built, hubs = roads.build_rooms()
        exits = {vnum: dict(room.exits) for vnum, room in built.items()}
        for name, area, vnum, hub, heading, start, end in roads.DESTINATIONS:
            exits[vnum] = {roads.REVERSE[heading]: hubs[hub]}
        routes = {
            ("Leaf", "Stone"): 197,
            ("Leaf", "Cloud"): 212,
            ("Leaf", "Sand"): 182,
            ("Stone", "Cloud"): 248,
            ("Stone", "Sand"): 217,
        }
        entry = {name: vnum for name, area, vnum, hub, d, start, end
                 in roads.DESTINATIONS}
        for (start, end), expected in routes.items():
            with self.subTest(start=start, end=end):
                self.assertEqual(distance(exits, entry[start], entry[end]), expected)
                self.assertGreaterEqual(expected, 100)
                self.assertLessEqual(expected, 250)
        # Sand -> Cloud is intentionally an indirect, two-stage journey.
        self.assertEqual(distance(exits, entry["Sand"], entry["Cloud"]), 392)

    def test_road_bends_without_jagged_switchbacks(self):
        for a, b, steps, first, end_port, title, biome in roads.SEGMENTS:
            if steps < 18:
                continue
            headings = roads._headings(first, roads.REVERSE[end_port], steps)
            turns = sum(x != y for x, y in zip(headings, headings[1:]))
            self.assertGreaterEqual(turns, 2, title)
            self.assertLessEqual(turns, steps // 4, title)
            for x, y in zip(headings, headings[1:]):
                diff = abs(roads.HEADINGS.index(x) - roads.HEADINGS.index(y))
                self.assertLessEqual(min(diff, 8 - diff), 1, title)


class OneTimeInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = tmp.name
        rooms = {
            9: world.Room(9, "Custom Konoha Gate", "Keep this exact text."),
            2501: world.Room(2501, "Stone Kage Chamber", "Preserve room."),
            7501: world.Room(7501, "Cloud Kage Chamber", "Preserve room."),
            10001: world.Room(10001, "Sand Kage Chamber", "Preserve room."),
        }
        rooms[9].exits["inside"] = 8
        rooms[2501].exits["inside"] = 2502
        self.patches = [
            patch.object(storage, "DATA_DIR", self.directory),
            patch.object(storage, "ACCOUNTS_DIR", os.path.join(self.directory, "accounts")),
            patch.object(storage, "PLAYERS_DIR", os.path.join(self.directory, "players")),
            patch.object(world.WORLD, "rooms", rooms),
            patch.object(areas, "all_areas", return_value=registered_areas()),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.initial = {
            "rooms": {str(vnum): asdict(room) for vnum, room in rooms.items()},
            "mobs": {"42": {"name": "Preserve mob"}},
            "items": {"9001": {"name": "Preserve item"}},
            "deleted_areas": [{"start": 50000, "end": 50010}],
            "custom": {"owner_data": True},
        }
        storage.save_world_state(self.initial)

    def test_merges_only_roads_and_entrance_exits(self):
        self.assertTrue(roads.install_once())
        state = storage.load_world_state()
        self.assertEqual(state["mobs"], self.initial["mobs"])
        self.assertEqual(state["items"], self.initial["items"])
        self.assertEqual(state["deleted_areas"], self.initial["deleted_areas"])
        self.assertEqual(state["custom"], self.initial["custom"])
        self.assertEqual(state["rooms"]["9"]["name"], "Custom Konoha Gate")
        self.assertEqual(state["rooms"]["9"]["description"], "Keep this exact text.")
        self.assertEqual(state["rooms"]["9"]["exits"]["inside"], 8)
        self.assertEqual(state["rooms"]["2501"]["exits"]["inside"], 2502)
        self.assertEqual(world.WORLD.rooms[20501].exits["north"], 9)
        self.assertEqual(world.WORLD.rooms[9].exits["south"], 20501)
        self.assertEqual(len([v for v in world.WORLD.rooms if 20501 <= v <= 30500]), 1528)
        for name, area, vnum, hub, d, start, end in roads.DESTINATIONS:
            self.assertEqual(world.WORLD.rooms[vnum].exits[roads.REVERSE[d]],
                             roads.build_rooms()[1][hub])
        self.assertTrue((Path(self.directory) / roads.MARKER_NAME).exists())
        self.assertTrue((Path(self.directory) / "world_state.json.bak").exists())

    def test_reboot_does_not_rebuild_or_overwrite_player_edits(self):
        self.assertTrue(roads.install_once())
        world.WORLD.rooms[20501].name = "Custom player road title"
        state = storage.load_world_state()
        state["rooms"]["20501"]["name"] = "Custom player road title"
        storage.save_world_state(state)
        self.assertFalse(roads.install_once())
        self.assertEqual(storage.load_world_state()["rooms"]["20501"]["name"],
                         "Custom player road title")

    def test_converts_only_mainland_area_from_prototype_to_live(self):
        entries = registered_areas()
        entries["mainland road network"]["prototype"] = True
        entries["mainland road network"]["prototype_owner"] = "biran"
        entries["leaf"]["prototype"] = True
        storage.save_areas(entries)
        self.assertTrue(roads.ensure_live_mainland_area())
        stored = storage.load_areas()
        self.assertIs(stored["mainland road network"]["prototype"], False)
        self.assertEqual(stored["mainland road network"]["prototype_owner"], "biran")
        self.assertTrue(stored["leaf"]["prototype"])
        self.assertFalse(roads.ensure_live_mainland_area())

    def test_repair_leaf_gate_without_overwriting_builder_rooms(self):
        self.assertTrue(roads.install_once())
        original = world.WORLD.rooms[9].description
        world.WORLD.rooms[9].exits.pop("south")
        saved = storage.load_world_state()
        saved["rooms"]["9"]["exits"].pop("south")
        storage.save_world_state(saved)
        self.assertTrue(roads.repair_leaf_gate())
        self.assertEqual(world.WORLD.rooms[9].exits["south"], 20501)
        self.assertEqual(world.WORLD.rooms[20501].exits["north"], 9)
        self.assertEqual(world.WORLD.rooms[9].description, original)
        self.assertEqual(storage.load_world_state()["rooms"]["9"]["exits"]["inside"], 8)
        self.assertFalse(roads.repair_leaf_gate())

    def test_repair_refuses_unfinished_room_20501(self):
        self.assertTrue(roads.install_once())
        world.WORLD.rooms[20501].name = "An Unfinished Room"
        world.WORLD.rooms[9].exits.pop("south")
        saved = storage.load_world_state()
        saved["rooms"]["20501"]["name"] = "An Unfinished Room"
        saved["rooms"]["9"]["exits"].pop("south")
        storage.save_world_state(saved)
        self.assertFalse(roads.repair_leaf_gate())
        self.assertNotIn("south", world.WORLD.rooms[9].exits)
        self.assertNotIn("south", storage.load_world_state()["rooms"]["9"]["exits"])
        self.assertEqual(world.WORLD.rooms[20501].name, "An Unfinished Room")

    def test_repair_leaf_gate_preserves_occupied_south_exit(self):
        self.assertTrue(roads.install_once())
        world.WORLD.rooms[9].exits["south"] = 10
        saved = storage.load_world_state()
        saved["rooms"]["9"]["exits"]["south"] = 10
        storage.save_world_state(saved)
        self.assertFalse(roads.repair_leaf_gate())
        self.assertEqual(world.WORLD.rooms[9].exits["south"], 10)
        self.assertEqual(storage.load_world_state()["rooms"]["9"]["exits"]["south"], 10)

    def test_occupied_road_vnum_refuses_entire_migration(self):
        world.WORLD.add_room(world.Room(20501, "Player already built here", "Do not delete"))
        with self.assertRaises(roads.RoadInstallationError):
            roads.install_once()
        self.assertEqual(storage.load_world_state(), self.initial)
        self.assertFalse((Path(self.directory) / roads.MARKER_NAME).exists())
        self.assertEqual(world.WORLD.rooms[20501].name, "Player already built here")

    def test_taken_leaf_exit_refuses_entire_migration(self):
        world.WORLD.rooms[9].exits["south"] = 11
        with self.assertRaisesRegex(roads.RoadInstallationError, "south exit"):
            roads.install_once()
        self.assertEqual(storage.load_world_state(), self.initial)
        self.assertFalse((Path(self.directory) / roads.MARKER_NAME).exists())

    def test_missing_country_area_refuses_entire_migration(self):
        incomplete = registered_areas()
        incomplete.pop("land of sound")
        with patch.object(areas, "all_areas", return_value=incomplete):
            with self.assertRaisesRegex(roads.RoadInstallationError, "land of sound"):
                roads.install_once()
        self.assertEqual(storage.load_world_state(), self.initial)
        self.assertFalse((Path(self.directory) / roads.MARKER_NAME).exists())


if __name__ == "__main__":
    unittest.main()
