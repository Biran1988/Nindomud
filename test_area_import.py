"""Offline area packages validate, import together, and survive reboot."""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import area_import
import combat
import olc
import spawn_points
import storage
import world
import world_persistence
from models import Player


def package():
    return {
        "format": "nindo-area-v1",
        "area": {"name": "Test Forest", "vnum_start": 20000, "vnum_end": 20999,
                 "reset_message": "The forest rustles."},
        "rooms": [
            {"vnum": 20000, "name": "Trail", "description": "A shaded trail.",
             "sector": "forest", "biome": "forest", "safe": False,
             "flags": [], "exits": {"east": 20001}, "x": 100, "y": 100},
            {"vnum": 20001, "name": "Glade", "description": "A quiet clearing.",
             "sector": "forest", "biome": "forest", "safe": True,
             "flags": [], "exits": {"west": 20000}, "x": 320, "y": 100},
        ],
        "mobs": [{"vnum": 30000, "name": "Forest Bandit", "level": 12,
                  "health": 250, "damage_min": 8, "damage_max": 14,
                  "room_vnum": 20000, "respawns": True}],
        "items": [{"vnum": 40000, "name": "Wild Berry", "item_type": "food",
                   "cost": 25, "room_vnum": 20001}],
    }


class AreaImportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        for name, value in (("DATA_DIR", tmp.name),
                            ("ACCOUNTS_DIR", os.path.join(tmp.name, "accounts")),
                            ("PLAYERS_DIR", os.path.join(tmp.name, "players"))):
            p = patch.object(storage, name, value)
            p.start(); self.addCleanup(p.stop)
        for target, name in ((world.WORLD, "rooms"), (combat, "MOB_TEMPLATES"),
                             (combat, "MOBS_BY_ROOM"), (olc, "OBJECT_TEMPLATES")):
            p = patch.object(target, name, {})
            p.start(); self.addCleanup(p.stop)
        p = patch.object(olc, "_log")
        p.start(); self.addCleanup(p.stop)
        world.WORLD.add_room(world.Room(1, "Existing room", "Keep me."))
        os.makedirs(os.path.join(tmp.name, "area_imports"))
        self.path = os.path.join(tmp.name, "area_imports", "test-forest.json")
        self.write(package())
        self.owner = NS(account=NS(name="Biran", staff_level="implementor"),
                        player=Player("Biran", "Biran", room_vnum=1), send=Mock())

    def write(self, payload):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(payload, file)

    def test_check_import_and_reboot_round_trip(self):
        olc.cmd_area(self.owner, ["import", "test-forest.json", "check"])
        self.assertIn("No changes made", self.owner.send.call_args.args[0])
        self.assertNotIn(20000, world.WORLD.rooms)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("Imported Test Forest", self.owner.send.call_args.args[0])
        self.assertEqual(world.WORLD.rooms[20000].exits["east"], 20001)
        self.assertEqual(world.WORLD.rooms[1].description, "Keep me.")
        self.assertEqual(len(spawn_points.list_spawn_points()), 2)
        self.assertEqual(len(combat.MOBS_BY_ROOM[20000]), 1)
        self.assertIn("Wild Berry", world.WORLD.rooms[20001].ground_items)
        self.assertIn("20000", storage.load_world_state()["rooms"])
        self.assertIn("test forest", storage.load_areas())

        world.WORLD.rooms.clear()
        combat.MOB_TEMPLATES.clear()
        combat.MOBS_BY_ROOM.clear()
        olc.OBJECT_TEMPLATES.clear()
        spawn_points.restore_custom_templates()
        world_persistence.apply_saved_world()
        spawn_points.apply_all()
        self.assertEqual(world.WORLD.rooms[1].description, "Keep me.")
        self.assertEqual(world.WORLD.rooms[20001].exits["west"], 20000)
        self.assertEqual(len(combat.MOBS_BY_ROOM[20000]), 1)
        self.assertIn("Wild Berry", world.WORLD.rooms[20001].ground_items)

    def test_invalid_package_and_repeated_import_change_nothing(self):
        bad = package()
        bad["rooms"][0]["exits"]["east"] = 55555
        self.write(bad)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("refused", self.owner.send.call_args.args[0])
        self.assertEqual(set(world.WORLD.rooms), {1})
        self.assertEqual(storage.load_areas(), {})
        self.write(package())
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        before = storage.load_world_state()
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("refused", self.owner.send.call_args.args[0])
        self.assertEqual(storage.load_world_state(), before)

    def test_export_edit_existing_area_and_preserve_advanced_fields(self):
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        world.WORLD.rooms[20000].programs = [{"trigger": "enter", "action": "echo", "args": "Hello"}]
        combat.MOB_TEMPLATES[30000]["shop_items"] = [40000]
        combat.MOB_TEMPLATES[30000]["damage_dice"] = "2d6+3"
        point_key = spawn_points._key("mob", 30000, 20000)
        points = storage.load_spawn_points()
        points["points"][point_key]["total_cap"] = 2
        storage.save_spawn_points(points)
        path, exported = area_import.export_area("Test Forest")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(exported["rooms"][0]["exits"]["east"], 20001)
        self.assertGreater(exported["rooms"][1]["x"], exported["rooms"][0]["x"])
        self.assertEqual(exported["rooms"][1]["y"], exported["rooms"][0]["y"])
        self.assertEqual(exported["mobs"][0]["room_vnum"], 20000)
        exported["rooms"][0]["description"] = "A winding shaded trail."
        exported["rooms"][0]["flags"] = ["CapturePoint"]
        exported["rooms"][0]["x"] = 480
        exported["rooms"][0]["y"] = 480
        exported["rooms"].append({"vnum": 20002, "name": "Lookout", "description": "A high ledge.",
                                  "exits": {"west": 20001}, "x": 192, "y": 0})
        exported["rooms"][1]["exits"]["east"] = 20002
        exported["mobs"][0]["name"] = "Forest Scout"
        exported["items"][0]["cost"] = 30
        self.write(exported)
        olc.cmd_area(self.owner, ["import", "test-forest.json", "check"])
        self.assertIn("valid for update", self.owner.send.call_args.args[0])
        self.assertNotIn(20002, world.WORLD.rooms)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("Updated Test Forest", self.owner.send.call_args.args[0])
        self.assertEqual(world.WORLD.rooms[20000].description, "A winding shaded trail.")
        self.assertIn("CapturePoint", world.WORLD.rooms[20000].flags)
        self.assertEqual(world.WORLD.rooms[20000].programs[0]["args"], "Hello")
        self.assertEqual(world.WORLD.rooms[20002].exits["west"], 20001)
        self.assertEqual(combat.MOB_TEMPLATES[30000]["shop_items"], [40000])
        self.assertEqual(combat.MOB_TEMPLATES[30000]["damage_dice"], "2d6+3")
        self.assertEqual(combat.MOB_TEMPLATES[30000]["short_desc"], "Forest Scout")
        self.assertEqual(olc.OBJECT_TEMPLATES[40000]["cost"], 30)
        self.assertEqual(storage.load_spawn_points()["points"][point_key]["total_cap"], 2)
        self.assertEqual(len(combat.MOBS_BY_ROOM[20000]), 1)
        _, refreshed = area_import.export_area("Test Forest")
        self.assertEqual(refreshed["rooms"][0]["x"], 480)
        self.assertEqual(refreshed["rooms"][0]["y"], 480)

    def test_stale_or_incomplete_existing_area_update_is_rejected(self):
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        _, exported = area_import.export_area("Test Forest")
        exported["rooms"][0]["description"] = "Edited offline."
        world.WORLD.rooms[20000].description = "Edited in game."
        self.write(exported)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("changed since export", self.owner.send.call_args.args[0])
        self.assertEqual(world.WORLD.rooms[20000].description, "Edited in game.")
        world.WORLD.rooms[20000].description = "A shaded trail."
        exported["rooms"].pop()
        self.write(exported)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("missing", self.owner.send.call_args.args[0])

    def test_existing_area_keeps_outside_links_and_rejects_foreign_vnums(self):
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        world.WORLD.rooms[20000].exits["north"] = 1
        _, exported = area_import.export_area("Test Forest")
        self.assertEqual(exported["rooms"][0]["exits"]["north"], 1)
        exported["rooms"][0]["name"] = "Trail Entrance"
        self.write(exported)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("Updated", self.owner.send.call_args.args[0])
        self.assertEqual(world.WORLD.rooms[20000].exits["north"], 1)
        _, exported = area_import.export_area("Test Forest")
        exported["mobs"].append({"vnum": 30001, "name": "Other Area Mob", "level": 1,
                                 "health": 10, "damage_min": 1, "damage_max": 2,
                                 "room_vnum": 20001})
        combat.MOB_TEMPLATES[30001] = combat.default_template(30001, "Protected")
        self.write(exported)
        olc.cmd_area(self.owner, ["import", "test-forest.json"])
        self.assertIn("already in use outside", self.owner.send.call_args.args[0])
        self.assertEqual(combat.MOB_TEMPLATES[30001]["short_desc"], "Protected")

    def test_import_path_and_permission_restrictions(self):
        for bad in ("../test-forest.json", "/tmp/test-forest.json", "other.txt"):
            with self.subTest(name=bad), self.assertRaises(ValueError):
                area_import.load_package(bad)
        builder = NS(account=NS(name="Other", staff_level="builder"),
                     player=Player("Other", "Other", room_vnum=1), send=Mock())
        olc.cmd_area(builder, ["import", "test-forest.json"])
        self.assertEqual(set(world.WORLD.rooms), {1})


if __name__ == "__main__":
    unittest.main()
