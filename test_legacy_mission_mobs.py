"""Legacy mission-only creatures cannot return from source or saved spawns."""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import combat
import legacy_mission_mobs as retired
import missions
import storage
from models import Player


class LegacyMissionMobTests(unittest.TestCase):
    def test_all_six_village_sets_and_four_rank_tiers_are_retired(self):
        self.assertEqual(len(retired.LEGACY_MOB_VNUMS), 30)
        for base in range(5001, 5007):
            for offset in (0, 100, 200, 300, 400):
                self.assertTrue(retired.is_legacy_mob(base + offset))
        self.assertFalse(retired.is_legacy_mob(6005))
        self.assertFalse(retired.is_legacy_mob(7001))

    def test_old_ids_cannot_be_chosen_even_if_saved_as_mission_mobs(self):
        templates = {
            5001: {"short_desc": "retired bandit", "level": 8, "act_flags": ["Mission"]},
            5101: {"short_desc": "retired rogue", "level": 8, "act_flags": ["Mission"]},
            7001: {"short_desc": "builder's enemy", "level": 8, "act_flags": ["Mission"]},
        }
        p = Player("Test", "test", level=8, village="leaf")
        with patch.object(combat, "MOB_TEMPLATES", templates):
            selected, _ = missions.pick_mission_mob(p, "D-Rank")
            self.assertEqual(selected, 7001)
            templates.pop(7001)
            self.assertEqual(missions.pick_mission_mob(p, "D-Rank"), (None, None))

    def test_old_board_hunts_use_new_picked_targets(self):
        for village, board in missions.MISSIONS.items():
            hunts = [m for m in board if m.get("mission_type") == "kill"]
            for mission in hunts:
                self.assertIsNone(mission.get("target_mob_template"))

    def test_retirement_removes_only_legacy_saved_templates_spawns_and_instances(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(storage, "DATA_DIR", tmp), \
                patch.object(combat, "MOB_TEMPLATES", {5001: {"name": "old"}, 7001: {"name": "new"}}), \
                patch.object(combat, "MOBS_BY_ROOM", {
                    1: [SimpleNamespace(template_vnum=5001), SimpleNamespace(template_vnum=7001)],
                }), \
                patch.object(combat, "_respawn_queue", [(10, 5001, 1), (20, 7001, 1)]):
            points = {"points": {
                "mob:5001:1": {"kind": "mob", "vnum": 5001, "room_vnum": 1},
                "mob:7001:1": {"kind": "mob", "vnum": 7001, "room_vnum": 1},
                "item:5001:1": {"kind": "item", "vnum": 5001, "room_vnum": 1},
            }}
            storage.save_spawn_points(points)
            storage.save_custom_templates({"mobs": {
                "5001": {"short_desc": "retired"}, "7001": {"short_desc": "new"}},
                "items": {"5001": {"short_desc": "unrelated item"}}})
            storage.save_world_state({"rooms": {"1": {"name": "Unrelated room"}},
                "mobs": {"5001": {"short_desc": "retired"}, "7001": {"short_desc": "new"}},
                "items": {"5001": {"short_desc": "safe"}}})
            self.assertEqual(retired.retire_saved_mobs(), (1, 1, 1))
            self.assertEqual(retired.retire_saved_mobs(), (0, 0, 0))
            self.assertEqual(set(storage.load_spawn_points()["points"]),
                             {"mob:7001:1", "item:5001:1"})
            saved = storage.load_custom_templates()
            self.assertEqual(set(saved["mobs"]), {"7001"})
            self.assertIn("5001", saved["items"])
            world = storage.load_world_state()
            self.assertEqual(set(world["mobs"]), {"7001"})
            self.assertIn("1", world["rooms"])
            self.assertIn("5001", world["items"])
            self.assertEqual(set(combat.MOB_TEMPLATES), {7001})
            self.assertEqual([m.template_vnum for m in combat.MOBS_BY_ROOM[1]], [7001])
            self.assertEqual(combat._respawn_queue, [(20, 7001, 1)])

    def test_active_saved_hunts_to_removed_mobs_are_retired_without_rewards(self):
        p = Player("Tester", "tester", village="leaf", level=25)
        p.active_missions = [
            {"mission_id": "leaf_d1", "progress": 0},
            {"mission_id": "dynamic_C-Rank_5101_old", "progress": 0,
             "dynamic": {"mission_id": "dynamic_C-Rank_5101_old",
                         "mission_type": "kill", "target_mob_template": 5101,
                         "title": "Old rogue", "rank": "C-Rank", "target_count": 1}},
        ]
        before = (p.ryo, p.experience, p.mission_points)
        messages = missions.expire_missions(p, now=1000)
        self.assertEqual(len(messages), 2)
        self.assertEqual(p.active_missions, [])
        self.assertEqual((p.ryo, p.experience, p.mission_points), before)


if __name__ == "__main__":
    unittest.main()
