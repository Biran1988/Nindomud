"""Regression tests for restoring missing roads without resetting any village."""
import collections
import os
import tempfile
import unittest
from dataclasses import asdict
from unittest.mock import patch

import areas
import mainland_roads
import mainland_recovery
import storage
import world


def reachable(rooms, start, end):
    todo = collections.deque([start])
    seen = set()
    while todo:
        room = todo.popleft()
        if room == end:
            return True
        if room in seen or room not in rooms:
            continue
        seen.add(room)
        todo.extend(rooms[room].exits.values())
    return False


class MainlandRestorationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        original, _ = mainland_roads.build_rooms()
        # The supplied room list shows 20501 unfinished and 21501..22028.
        remaining = {v: r for v, r in original.items() if v >= 21501}
        remaining[20501] = world.Room(20501, "An Unfinished Room", "A saved placeholder.")
        for vnum, name in ((9, "Existing Leaf Gate"), (2501, "Stone Kage"),
                           (7501, "Cloud Kage"), (10001, "Sand Kage")):
            r = world.Room(vnum, name, f"Keep custom {name} description.")
            r.exits["inside"] = vnum + 1
            remaining[vnum] = r
        self.saved_start = {
            "rooms": {str(v): asdict(r) for v, r in remaining.items()},
            "items": {"999": {"keep": "YES"}},
            "mobs": {"123": {"name": "Don't touch"}},
            "players": {"name": "Preserve"},
            "custom": {"flag": True},
        }
        self.patches = [
            patch.object(storage, "DATA_DIR", self.folder),
            patch.object(storage, "ACCOUNTS_DIR", os.path.join(self.folder, "accounts")),
            patch.object(storage, "PLAYERS_DIR", os.path.join(self.folder, "players")),
            patch.object(world.WORLD, "rooms", remaining),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        storage.save_areas({"mainland road network": {
            "name": "Mainland Road Network", "vnum_start": 20501,
            "vnum_end": 30500, "creator": "system", "prototype": False,
        }, **{
            n.lower(): {"name": n, "vnum_start": a, "vnum_end": b,
                        "creator": "system"}
            for n, a, b in (
                ("Land of Grass", 12501, 13500),
                ("Land of Rain", 13501, 14500),
                ("Land of Rivers", 14501, 15500),
                ("Land of Birds", 15501, 16500),
                ("Land of Waterfalls", 16501, 17500),
                ("Land of Sound", 17501, 18500),
                ("Land of Frost", 18501, 19500),
                ("Land of Hot Water", 19501, 20500),
            )
        }})
        storage.save_world_state(self.saved_start)

    def test_recovers_missing_thousand_rooms_and_leaf_all_anki_gates(self):
        result = mainland_recovery.repair_missing_roads()
        self.assertEqual(result["restored_rooms"], 999)
        self.assertEqual(result["replaced_unfinished"], 1)
        self.assertEqual(world.WORLD.get(20501).name, "Konoha Southern Crossroads")
        self.assertEqual(len([v for v in world.WORLD.rooms if 20501 <= v <= 22028]), 1528)
        self.assertEqual(world.WORLD.get(9).exits["south"], 20501)
        self.assertEqual(world.WORLD.get(20501).exits["north"], 9)
        for entrance in (2501, 7501, 10001, 12501, 13501, 14501,
                         15501, 16501, 17501, 18501, 19501):
            self.assertTrue(reachable(world.WORLD.rooms, 9, entrance),
                            f"Leaf must connect to {entrance}")
            self.assertTrue(reachable(world.WORLD.rooms, entrance, 9),
                            f"{entrance} must return to Leaf")
        saved = storage.load_world_state()
        for key in ("items", "mobs", "players", "custom"):
            self.assertEqual(saved[key], self.saved_start[key])
        for vnum in (9, 2501, 7501, 10001):
            original = self.saved_start["rooms"][str(vnum)]
            current = saved["rooms"][str(vnum)]
            for field in original:
                if field != "exits":
                    self.assertEqual(current[field], original[field])
            self.assertEqual(current["exits"]["inside"], vnum + 1)
        followup = mainland_recovery.repair_missing_roads()
        self.assertEqual(followup["updated_rooms"], 0)

    def test_preserves_existing_leaf_south_exit_by_using_another_direction(self):
        world.WORLD.get(9).exits["south"] = 42
        original = storage.load_world_state()
        original["rooms"]["9"]["exits"]["south"] = 42
        storage.save_world_state(original)
        mainland_recovery.repair_missing_roads()
        self.assertEqual(world.WORLD.get(9).exits["south"], 42)
        self.assertTrue(reachable(world.WORLD.rooms, 9, 21501))
        self.assertTrue(reachable(world.WORLD.rooms, 21501, 9))

    def test_unrelated_road_range_room_blocks_overwrite_without_partial_save(self):
        world.WORLD.rooms[21000] = world.Room(
            21000, "Builder's custom shrine", "Preserve this instead of replacing it.")
        with self.assertRaises(mainland_recovery.RoadRecoveryError):
            mainland_recovery.repair_missing_roads()
        self.assertEqual(storage.load_world_state(), self.saved_start)
        self.assertEqual(world.WORLD.get(20501).name, "An Unfinished Room")


if __name__ == "__main__":
    unittest.main()
