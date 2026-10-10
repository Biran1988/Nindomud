"""Builder assignments, prototype links, and Biran-only area deletion."""

import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import areas
import combat
import commands
import olc
import spawn_points
import storage
import world
import world_persistence
from models import Account, Player


class AreaSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patches = [patch.object(storage, "DATA_DIR", self.temp.name),
                        patch.object(world.WORLD, "rooms", {}),
                        patch.object(combat, "MOBS_BY_ROOM", {}),
                        patch.object(combat, "MOB_TEMPLATES", {}),
                        patch.object(olc, "OBJECT_TEMPLATES", {}),
                        patch.object(olc, "_log")]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        areas.register_area("Live", 100, 199, "system")
        areas.register_area("Alpha", 200, 299, "Biran")
        areas.register_area("Alpha Two", 300, 399, "Biran")
        areas.register_area("Beta", 400, 499, "Biran")
        for vnum in (100, 200, 201, 300, 400):
            world.WORLD.add_room(world.Room(vnum, str(vnum), "Test room"))
        self.builder = NS(account=NS(name="Alice", staff_level="builder"),
                          player=Player("Alice", "Alice", room_vnum=200), send=Mock())
        self.biran = NS(account=NS(name="biran", staff_level="implementor"),
                        player=Player("Biran", "biran", room_vnum=100),
                        send=Mock(), active_sessions=lambda: [])

    def test_builder_requires_assignment_for_movement_and_prototypes(self):
        self.assertFalse(olc._require_assigned_vnum(self.builder, 200))
        areas.set_builder_assignment("Alpha", "Alice", True)
        self.assertTrue(olc._require_assigned_vnum(self.builder, 201))
        self.assertFalse(olc._require_assigned_vnum(self.builder, 300))
        olc.cmd_mset(self.builder, ["create", "400", "other", "mob"])
        self.assertNotIn(400, combat.MOB_TEMPLATES)
        olc.cmd_mset(self.builder, ["create", "201", "my", "mob"])
        self.assertIn(201, combat.MOB_TEMPLATES)

    def test_links_obey_prototype_status_and_owner(self):
        areas.set_builder_assignment("Alpha", "Alice", True)
        areas.set_builder_assignment("Alpha Two", "Alice", True)
        areas.set_builder_assignment("Beta", "Bob", True)
        self.assertTrue(olc._require_exit_link(self.builder, 200, 201))
        self.assertTrue(olc._require_exit_link(self.builder, 200, 300))
        self.assertFalse(olc._require_exit_link(self.builder, 200, 400))
        self.assertFalse(olc._require_exit_link(self.builder, 200, 100))
        areas.set_prototype("Alpha Two", False)
        self.assertFalse(olc._require_exit_link(self.builder, 200, 300))
        self.assertTrue(olc._require_exit_link(self.biran, 200, 100))

    def test_only_biran_with_code_can_delete_area(self):
        areas.set_builder_assignment("Alpha", "Alice", True)
        self.builder.active_sessions = lambda: []
        olc.cmd_area(self.builder, ["delete", "Alpha", "1988"])
        self.assertIsNotNone(areas.find_area("Alpha"))
        olc.cmd_area(self.biran, ["delete", "Alpha", "bad"])
        self.assertIsNotNone(areas.find_area("Alpha"))
        olc.cmd_area(self.biran, ["delete", "Alpha", "1988"])
        self.assertIsNone(areas.find_area("Alpha"))
        self.assertNotIn(200, world.WORLD.rooms)
        self.assertIn(100, world.WORLD.rooms)
        state = storage.load_world_state()
        self.assertEqual(state["deleted_areas"][0]["name"], "Alpha")
        # Simulate hardcoded content being rebuilt on reboot. The saved
        # deletion must remove it even though a plain snapshot cannot.
        world.WORLD.add_room(world.Room(200, "Rebuilt", "Built in content"))
        world.WORLD.rooms[100].exits["east"] = 200
        world_persistence.apply_saved_world()
        self.assertNotIn(200, world.WORLD.rooms)
        self.assertNotIn("east", world.WORLD.rooms[100].exits)

    def test_imms_lists_staff_rank_and_presence(self):
        storage.save_account(Account("Alice", "", "", staff_level="builder"))
        storage.save_account(Account("biran", "", "", staff_level="implementor"))
        storage.save_account(Account("Civilian", "", ""))
        viewer = NS(player=Player("Viewer", "Viewer"), send=Mock(),
                    active_sessions=lambda: [self.builder])
        commands.cmd_imms(viewer, [])
        message = viewer.send.call_args.args[0]
        self.assertIn("Alice - Builder", message)
        self.assertIn("biran - Implementor", message)
        self.assertNotIn("Civilian", message)
        self.assertIn("online", message)

    def test_delete_removes_exclusive_templates_and_keeps_shared_ones(self):
        combat.MOB_TEMPLATES[205] = combat.default_template(205, "area mob")
        olc.OBJECT_TEMPLATES[206] = olc.default_object(206, "area item")
        olc.OBJECT_TEMPLATES[207] = olc.default_object(207, "shared item")
        self.assertEqual(spawn_points.add_spawn_point("mob", 205, 200), "")
        self.assertEqual(spawn_points.add_spawn_point("item", 206, 200), "")
        self.assertEqual(spawn_points.add_spawn_point("item", 207, 200), "")
        self.assertEqual(spawn_points.add_spawn_point("item", 207, 100), "")
        world.WORLD.rooms[100].exits["east"] = 200
        olc.cmd_area(self.biran, ["delete", "Alpha", "1988"])
        self.assertNotIn(205, combat.MOB_TEMPLATES)
        self.assertNotIn(206, olc.OBJECT_TEMPLATES)
        self.assertIn(207, olc.OBJECT_TEMPLATES)
        self.assertNotIn("east", world.WORLD.rooms[100].exits)
        self.assertEqual([p["room_vnum"] for p in spawn_points.list_spawn_points()], [100])

    def test_deletion_reapplies_after_late_built_in_rooms(self):
        olc.cmd_area(self.biran, ["delete", "Alpha", "1988"])
        world.WORLD.add_room(world.Room(200, "Late built in", "Rebuilt after snapshot"))
        world.WORLD.rooms[100].exits["east"] = 200
        world_persistence.apply_deleted_areas()
        self.assertNotIn(200, world.WORLD.rooms)
        self.assertNotIn("east", world.WORLD.rooms[100].exits)


if __name__ == "__main__":
    unittest.main()
