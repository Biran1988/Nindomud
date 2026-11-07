"""Regression tests for the additive mainland camps and roadside inns."""
import collections
import tempfile
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import mainland_roads
import mob_aggression
import roadside_encounters as roadside
import storage
import world


def road_distances(roads, first):
    frontier = collections.deque([(first, 0)])
    distance = {}
    while frontier:
        room, steps = frontier.popleft()
        if room in distance or room not in roads:
            continue
        distance[room] = steps
        for neighbor in roads[room].exits.values():
            if neighbor not in distance:
                frontier.append((neighbor, steps + 1))
    return distance


class GeometryTests(unittest.TestCase):
    def test_all_five_camps_and_five_inns_have_distinct_road_spurs(self):
        rooms, links, templates, points, info = roadside.build_plan()
        self.assertEqual(len(info["camps"]), 5)
        self.assertEqual(len(info["inns"]), 5)
        self.assertEqual(len(rooms), 130)  # five 17-room camps and five nine-room inns
        self.assertEqual(len(links), 10)
        self.assertEqual(len(templates), 30)
        self.assertEqual(len(points), 150)  # 26 per camp + one keeper/three villagers per inn
        self.assertEqual(sorted(rooms), list(range(22029, 22159)))
        self.assertEqual(len({a for a, _, _ in links}), 10)
        for origin, direction, first in links:
            self.assertEqual(rooms[first].exits[roadside.REVERSE[direction]], origin)
            self.assertNotIn(origin, rooms)

    def test_all_camp_anchors_are_at_least_fifty_from_every_mainland_village(self):
        roads, hubs = mainland_roads.build_rooms()
        distances = [road_distances(roads, hubs[k])
                     for k in ("leaf_gate", "stone", "cloud", "sand")]
        _, _, _, _, info = roadside.build_plan()
        for camp in info["camps"].values():
            for distance in distances:
                # A village entrance is one additional step from its road hub.
                self.assertGreaterEqual(distance[camp["anchor"]] + 1, 50)

    def test_twenty_two_camp_residents_plus_four_roaming_outposts(self):
        _, _, templates, points, info = roadside.build_plan()
        for index, (key, *_) in enumerate(roadside.CAMPS):
            camp = info["camps"][key]
            self.assertEqual(camp["mob_count"], 26)
            self.assertEqual(len(camp["camp"]), 13)
            self.assertEqual(len(camp["trail"]), 4)
            core = [p for p in points.values()
                    if p["room_vnum"] in camp["camp"]]
            self.assertEqual(len(core), 22)
            outside = [p for p in points.values()
                       if p["vnum"] in range(roadside.MOB_BASE+6*index,
                                            roadside.MOB_BASE+6*index+4)
                       and p["room_vnum"] not in camp["camp"]]
            self.assertEqual(len(outside), 4)
            for kind in range(4):
                template = templates[roadside.MOB_BASE+6*index+kind]
                self.assertIn("Wander", template["act_flags"])
                self.assertIn("aggressive_everyone", template["act_flags"])
                self.assertIn("roadside_weapon", template)
                self.assertIn(camp["anchor"], template["roadside_patrol_vnums"])
                self.assertIn(camp["camp"][0], template["roadside_patrol_vnums"])

    def test_spur_avoids_builder_occupied_highway_exit(self):
        roads, _ = mainland_roads.build_rooms()
        initial_rooms, original_links, _, _, _ = roadside.build_plan()
        anchor, originally_preferred, first = original_links[0]
        custom_road = roads[anchor]
        custom_road.exits[originally_preferred] = 99999  # builder-owned spur
        changed_rooms, changed_links, _, _, _ = roadside.build_plan(road_rooms=roads)
        new_anchor, new_direction, new_first = changed_links[0]
        self.assertEqual((new_anchor, new_first), (anchor, first))
        self.assertNotEqual(new_direction, originally_preferred)
        self.assertEqual(custom_road.exits[originally_preferred], 99999)
        self.assertEqual(changed_rooms[first].exits[roadside.REVERSE[new_direction]], anchor)

    def test_inns_charge_for_unlinked_safe_hospital_bath(self):
        rooms, _, _, _, info = roadside.build_plan()
        for inn in info["inns"].values():
            lobby, bath = rooms[inn["lobby"]], rooms[inn["bath"]]
            self.assertNotIn(bath.vnum, lobby.exits.values())  # no free entry
            self.assertEqual(bath.exits, {"outside": lobby.vnum})
            self.assertIn("accelerated_healing", bath.flags)
            self.assertTrue(bath.safe)
            self.assertEqual(len(inn["homes"]), 3)
            for home in inn["homes"]:
                self.assertTrue(rooms[home].safe)

    def test_bandits_stop_auto_aggression_at_double_their_level(self):
        _, _, templates, _, _ = roadside.build_plan()
        bandit = templates[roadside.MOB_BASE+1]
        player = SimpleNamespace(level=55, village="leaf", clan="")
        self.assertTrue(mob_aggression.targets_player(bandit, player, 28))
        player.level = 56
        self.assertFalse(mob_aggression.targets_player(bandit, player, 28))
        ordinary = {"act_flags": ["aggressive_everyone"]}
        self.assertTrue(mob_aggression.targets_player(ordinary, player, 28))


class InstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.patches = [
            patch.object(storage, "DATA_DIR", temp.name),
            patch.object(storage, "ACCOUNTS_DIR", temp.name+"/accounts"),
            patch.object(storage, "PLAYERS_DIR", temp.name+"/players"),
            patch.object(world.WORLD, "rooms", {}),
            patch.object(combat, "MOB_TEMPLATES", {}),
            patch.object(combat, "MOBS_BY_ROOM", {}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        all_roads, _ = mainland_roads.build_rooms()
        world.WORLD.rooms.update(all_roads)
        import areas
        patcher = patch.object(areas, "all_areas", return_value={
            "mainland": {"name": "Mainland Road Network",
                          "vnum_start": 20501, "vnum_end": 30500}
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.initial = {"rooms": {str(v): asdict(r) for v, r in all_roads.items()},
                        "mobs": {}, "items": {"812": {"name": "keep"}},
                        "players": {"test": True}, "extra": "keep"}
        storage.save_world_state(self.initial)

    def test_installs_once_and_retains_unrelated_world_data(self):
        self.assertTrue(roadside.install_once())
        saved = storage.load_world_state()
        self.assertEqual(saved["items"], self.initial["items"])
        self.assertEqual(saved["players"], self.initial["players"])
        self.assertEqual(saved["extra"], "keep")
        self.assertEqual(len(saved["mobs"]), 30)
        self.assertEqual(len(storage.load_spawn_points()["points"]), 150)
        self.assertEqual(len([v for v in world.WORLD.rooms if 22029 <= v <= 22158]), 130)
        self.assertEqual(sum(len(m) for m in combat.MOBS_BY_ROOM.values()), 150)
        self.assertFalse(roadside.install_once())

    def test_repair_restores_missing_camps_after_marker_survives(self):
        self.assertTrue(roadside.install_once())
        import json
        existing = storage.load_world_state()
        preserved = existing["items"]
        for vnum in range(22029, 22159):
            world.WORLD.rooms.pop(vnum)
            existing["rooms"].pop(str(vnum))
        storage.save_world_state(existing)
        old_points = storage.load_spawn_points()
        old_points["points"].clear()
        storage.save_spawn_points(old_points)
        self.assertFalse(roadside.install_once())  # marker already present
        result = roadside.repair_missing()
        self.assertEqual(result["restored_rooms"], 130)
        self.assertEqual(result["restored_spawnpoints"], 150)
        self.assertEqual(len([v for v in world.WORLD.rooms if 22029 <= v <= 22158]), 130)
        self.assertEqual(storage.load_world_state()["items"], preserved)
        self.assertEqual(roadside.repair_missing()["updated_rooms"], 0)

    def test_conflict_is_detected_before_any_saved_mutation(self):
        world.WORLD.add_room(world.Room(22029, "Builder's existing room", "Keep me"))
        with self.assertRaises(roadside.RoadsideInstallationError):
            roadside.install_once()
        self.assertEqual(storage.load_world_state(), self.initial)
        self.assertEqual(storage.load_spawn_points(), {})
        self.assertEqual(storage.load_custom_templates(), {"mobs": {}, "items": {}})


if __name__ == "__main__":
    unittest.main()
