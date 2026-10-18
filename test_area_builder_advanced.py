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

    def test_multiline_scripts_survive_area_import_and_export(self):
        data = package()
        data["rooms"][0]["builder"] = {
            "programs": [{"trigger": "enter", "script":
                          "if level($n) >= 10\nmpechoat Welcome to the forest.\nendif",
                          "chance": 100}]}
        data["mobs"][0]["settings"] = {
            "mob_programs": [{"trigger": "fight", "script":
                              "if random(30)\nsay This fight is not over!\nendif",
                              "chance": 30},
                             {"trigger": "give", "script":
                              "if object($o) == 40000\nmpheal 10\nendif",
                              "chance": 100}]}
        data["items"][0]["settings"] = {
            "item_programs": [{"trigger": "get", "script":
                               "mpechoat You found a rare item.", "chance": 100}]}
        staged = area_import.validate(data)
        area_import.import_package(staged, "Biran")
        self.assertIn("if level", world.WORLD.rooms[20000].programs[0]["script"])
        self.assertIn("if random", combat.MOB_TEMPLATES[30000]["mob_programs"][0]["script"])
        self.assertEqual(olc.OBJECT_TEMPLATES[40000]["item_programs"][0]["trigger"], "get")
        _, exported = area_import.export_area("Test Forest")
        self.assertIn("mpheal 10", exported["mobs"][0]["settings"]["mob_programs"][1]["script"])
        self.assertEqual(exported["items"][0]["settings"]["item_programs"][0]["chance"], 100)

    def test_reject_privileged_multiline_program_during_import(self):
        data = package()
        data["mobs"][0]["settings"] = {
            "mob_programs": [{"trigger": "greet",
                              "script": "mpforce promoteimm $n", "chance": 100}]}
        with self.assertRaisesRegex(ValueError, "mpforce"):
            area_import.validate(data)

    def test_rset_no_wander_flag_toggles_on_and_off(self):
        area_import.import_package(area_import.validate(package()), "Biran")
        self.owner.player.room_vnum = 20000
        olc.cmd_rset(self.owner, ["flags", "no_wander"])
        self.assertIn("no_wander", world.WORLD.rooms[20000].flags)
        olc.cmd_rset(self.owner, ["flags", "no_wander"])
        self.assertNotIn("no_wander", world.WORLD.rooms[20000].flags)

    def test_no_wander_flag_round_trips_with_area_and_world_save(self):
        import world_persistence
        data = package()
        data["rooms"][0]["flags"] = ["no_wander"]
        area_import.import_package(area_import.validate(data), "Biran")
        self.assertIn("no_wander", world.WORLD.rooms[20000].flags)
        _, exported = area_import.export_area("Test Forest")
        self.assertIn("no_wander", exported["rooms"][0]["flags"])
        world_persistence.save_world()
        self.assertIn("no_wander", storage.load_world_state()["rooms"]["20000"]["flags"])

    def test_mob_aggression_flags_target_fields_roundtrip(self):
        data = package()
        data["mobs"][0]["settings"] = {
            "act_flags": ["Npc", "aggressive_village", "aggressive_clan",
                          "aggressive_everyone"],
            "aggro_village": "leaf",
            "aggro_clan": "uchiha",
        }
        staged = area_import.validate(data)
        area_import.import_package(staged, "Biran")
        template = combat.MOB_TEMPLATES[30000]
        self.assertIn("aggressive_village", template["act_flags"])
        self.assertIn("aggressive_clan", template["act_flags"])
        self.assertIn("aggressive_everyone", template["act_flags"])
        self.assertEqual(template["aggro_village"], "leaf")
        self.assertEqual(template["aggro_clan"], "uchiha")
        _, exported = area_import.export_area("Test Forest")
        self.assertEqual(exported["mobs"][0]["settings"]["aggro_village"], "leaf")
        self.assertEqual(exported["mobs"][0]["settings"]["aggro_clan"], "uchiha")

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
