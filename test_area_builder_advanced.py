"""Advanced offline editor packages: safety, round trips, and persistent builder fields."""
import copy
import unittest

import area_import
import areas
import combat
import olc
import spawn_points
import storage
import world
from test_area_import import AreaImportTests, package


class AdvancedAreaEditorTests(unittest.TestCase):
    def setUp(self):
        AreaImportTests.setUp(self)

    def write(self, payload):
        AreaImportTests.write(self, payload)

    def test_advanced_builder_fields_apply_and_survive_export(self):
        data = package()
        data["area"]["income"] = 120
        data["rooms"][0]["builder"] = {
            "enabled": True, "apartment": False, "player_shop": False,
            "exit_flags": {"east": ["door", "locked"]},
            "exit_door_open": {"east": False}, "exit_key_item": {},
            "exit_passcode": {},
            "programs": [{"trigger": "enter", "action": "say",
                          "args": "The forest watches you."}],
        }
        data["mobs"][0]["settings"] = {
            "shopkeeper": True, "shop_items": [40000], "act_flags": ["Npc", "Sentinel"],
            "attributes": {"str": 17, "int": 12, "wis": 10, "dex": 19,
                           "con": 12, "cha": 10, "luck": 12},
            "mob_programs": [{"trigger": "death", "action": "give_ryo", "args": "50"}],
        }
        data["mobs"][0]["dice"] = {"damage_dice": "2d6+2"}
        data["mobs"][0]["spawn_caps"] = {"total_cap": 5, "per_period_cap": 2}
        data["items"][0]["settings"] = {
            "rarity": "rare", "weight": 4, "damage": 15,
            "item_programs": [{"trigger": "get", "action": "say", "args": "You found it!"}],
        }
        data["items"][0]["spawn_caps"] = {"total_cap": None, "per_period_cap": None}
        staged = area_import.validate(data)
        self.assertNotIn(20000, world.WORLD.rooms)
        area_import.import_package(staged, "Biran")
        room = world.WORLD.rooms[20000]
        self.assertEqual(room.exit_flags["east"], ["door", "locked"])
        self.assertFalse(room.exit_door_open["east"])
        self.assertEqual(room.programs[0]["trigger"], "enter")
        self.assertEqual(combat.MOB_TEMPLATES[30000]["damage_dice"], "2d6+2")
        self.assertTrue(combat.MOB_TEMPLATES[30000]["shopkeeper"])
        self.assertEqual(combat.MOB_TEMPLATES[30000]["shop_items"], [40000])
        self.assertEqual(olc.OBJECT_TEMPLATES[40000]["damage"], 15)
        self.assertEqual(spawn_points.get_spawn_caps("mob", 30000, 20000), (5, 2))
        self.assertEqual(areas.find_area("Test Forest").income, 120)
        _, exported = area_import.export_area("Test Forest")
        self.assertEqual(exported["rooms"][0]["builder"]["exit_flags"]["east"], ["door", "locked"])
        self.assertTrue(exported["mobs"][0]["settings"]["shopkeeper"])
        self.assertEqual(exported["items"][0]["settings"]["rarity"], "rare")
        self.assertIn("details", exported["source"]["baseline"])

    def test_edit_existing_area_keeps_unedited_advanced_fields(self):
        area_import.import_package(area_import.validate(package()), "Biran")
        world.WORLD.rooms[20000].programs = [
            {"trigger": "enter", "action": "say", "args": "Welcome."}]
        combat.MOB_TEMPLATES[30000]["shopkeeper"] = True
        olc.OBJECT_TEMPLATES[40000]["rarity"] = "rare"
        _, exported = area_import.export_area("Test Forest")
        exported["rooms"][0]["description"] = "Now a winding trail."
        exported["mobs"][0]["settings"]["shopkeeper"] = False
        exported["items"][0]["settings"]["rarity"] = "uncommon"
        exported["area"]["income"] = 10
        area_import.import_package(area_import.validate(exported), "Biran")
        self.assertEqual(world.WORLD.rooms[20000].description, "Now a winding trail.")
        self.assertEqual(world.WORLD.rooms[20000].programs[0]["args"], "Welcome.")
        self.assertFalse(combat.MOB_TEMPLATES[30000]["shopkeeper"])
        self.assertEqual(olc.OBJECT_TEMPLATES[40000]["rarity"], "uncommon")
        self.assertEqual(areas.find_area("Test Forest").income, 10)

    def test_reject_restricted_fields_and_executable_programs(self):
        data = package()
        data["mobs"][0]["settings"] = {"__class__": "oops"}
        with self.assertRaisesRegex(ValueError, "unknown or restricted"):
            area_import.validate(data)
        data["mobs"][0]["settings"] = {
            "mob_programs": [{"trigger": "death", "action": "__import__",
                              "args": "os"}]}
        with self.assertRaises(ValueError):
            area_import.validate(data)
        data["mobs"][0]["settings"] = {"shopkeeper": "yes"}
        with self.assertRaises(ValueError):
            area_import.validate(data)
        data["mobs"][0].pop("settings")
        data["rooms"][0]["builder"] = {"exit_flags": {"up": ["door"]}}
        with self.assertRaisesRegex(ValueError, "has no exit"):
            area_import.validate(data)
        self.assertEqual(storage.load_areas(), {})

    def test_stale_advanced_changes_refuse_import(self):
        area_import.import_package(area_import.validate(package()), "Biran")
        _, exported = area_import.export_area("Test Forest")
        combat.MOB_TEMPLATES[30000]["shopkeeper"] = True
        with self.assertRaisesRegex(ValueError, "advanced fields changed"):
            area_import.validate(exported)
        self.assertEqual(world.WORLD.rooms[20000].name, "Trail")

    def test_old_format_still_imports_without_advanced_fields(self):
        data = package()
        staged = area_import.validate(copy.deepcopy(data))
        self.assertEqual(staged["income"], None)
        area_import.import_package(staged, "Biran")
        self.assertEqual(world.WORLD.rooms[20001].name, "Glade")
