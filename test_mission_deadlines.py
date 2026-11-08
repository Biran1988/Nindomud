"""Regression tests for the 30-minute, level-tagged mission interface."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import combat
import commands
import missions
from models import Player


def player(level=50):
    return Player("Ninja", "ninja", village="leaf", level=level)


class MissionCommandTests(unittest.TestCase):
    def setUp(self):
        self.templates = {
            7001: {"short_desc": "a level-appropriate rogue", "level": 60,
                   "act_flags": ["Npc", "Mission"]},
            7002: {"short_desc": "an unmarked rogue", "level": 60,
                   "act_flags": ["Npc"]},
            7003: {"short_desc": "an overpowered rogue", "level": 250,
                   "act_flags": ["Npc", "Mission"]},
            7004: {"short_desc": "an easy rogue", "level": 6,
                   "act_flags": ["Npc", "Mission"]},
        }
        p = patch.object(combat, "MOB_TEMPLATES", self.templates)
        p.start()
        self.addCleanup(p.stop)

    def test_mission_command_is_registered(self):
        self.assertIs(commands.COMMANDS["mission"], commands.cmd_mission)

    def test_only_tagged_level_appropriate_hunts_are_assigned(self):
        ninja = player(level=50)
        with patch.object(missions.time, "time", return_value=1000):
            result = missions.request_mission(ninja, "c")
        self.assertIn("Mission requested", result)
        self.assertEqual(ninja.active_missions[0]["dynamic"]["target_mob_template"], 7001)
        self.assertEqual(ninja.active_missions[0]["expires_at"], 2800)
        self.assertEqual(ninja.active_missions[0]["progress"], 0)
        info = missions.mission_info(ninja, now=1000)
        self.assertIn("a level-appropriate rogue", info)
        self.assertIn("level 60", info)
        self.assertIn("0/1", info)
        self.assertIn("30m", info)
        self.assertNotIn("an unmarked rogue", info)

    def test_deadline_auto_fails_before_late_kill_can_award_rewards(self):
        ninja = player()
        with patch.object(missions.time, "time", return_value=1000):
            missions.request_mission(ninja, "c")
        old_ryo, old_points = ninja.ryo, ninja.mission_points
        with patch.object(missions.time, "time", return_value=2800):
            lines = missions.on_mob_defeated(ninja, 7001)
        self.assertIn("time limit", "\n".join(lines))
        self.assertEqual(ninja.active_missions, [])
        self.assertEqual(ninja.completed_missions, [])
        self.assertEqual((ninja.ryo, ninja.mission_points), (old_ryo, old_points))

    def test_deadline_survives_player_serialization_and_offline_time(self):
        ninja = player()
        with patch.object(missions.time, "time", return_value=1000):
            missions.request_mission(ninja, "c")
        loaded = Player.from_dict(ninja.to_dict())
        self.assertEqual(loaded.active_missions[0]["expires_at"], 2800)
        failed = missions.expire_missions(loaded, now=4000)
        self.assertEqual(len(failed), 1)
        self.assertEqual(loaded.active_missions, [])

    def test_mission_fail_abandons_without_rewards(self):
        ninja = player()
        with patch.object(missions.time, "time", return_value=1000):
            missions.request_mission(ninja, "c")
        result = missions.fail_mission(ninja)
        self.assertIn("Mission failed", result)
        self.assertEqual(ninja.active_missions, [])
        self.assertEqual(ninja.mission_points, 0)

    def test_mission_request_info_and_fail_dispatch(self):
        ninja = player()
        messages = []
        session = SimpleNamespace(player=ninja, send=messages.append)
        with patch.object(missions.time, "time", return_value=1000), \
                patch.object(commands.storage, "save_player") as save:
            commands.cmd_mission(session, ["request", "c"])
            commands.cmd_mission(session, ["info"])
            commands.cmd_mission(session, ["fail"])
        self.assertTrue(any("Mission requested" in m for m in messages))
        self.assertTrue(any("Hunt: a level-appropriate rogue" in m for m in messages))
        self.assertTrue(any("Mission failed" in m for m in messages))
        self.assertEqual(ninja.active_missions, [])
        self.assertGreaterEqual(save.call_count, 2)

    def test_board_rank_d_hunt_requires_tag_and_appropriate_level(self):
        ninja = player(level=6)
        result = missions.accept_mission(ninja, "leaf", "leaf_d1")
        self.assertIn("Mission accepted", result)
        self.assertEqual(ninja.active_missions[0]["dynamic"]["target_mob_template"], 7004)
        self.assertEqual(ninja.active_missions[0]["expires_at"] > 0, True)
        no_tagged = {7002: self.templates[7002]}
        with patch.object(combat, "MOB_TEMPLATES", no_tagged), \
                patch.object(missions, "_fallback_noncombat_mission",
                             return_value="Mission requested: Recovery") as fallback:
            another = missions.accept_mission(player(level=6), "leaf", "leaf_d1")
        self.assertIn("Mission requested: Recovery", another)
        fallback.assert_called_once()

    def test_existing_active_mission_receives_a_single_upgrade_deadline(self):
        ninja = player()
        ninja.active_missions.append({"mission_id": "leaf_d2", "progress": 1})
        self.assertEqual(missions.expire_missions(ninja, now=1000), [])
        self.assertEqual(ninja.active_missions[0]["expires_at"], 2800)
        self.assertEqual(missions.expire_missions(ninja, now=1500), [])
        self.assertEqual(ninja.active_missions[0]["expires_at"], 2800)
        self.assertEqual(len(missions.expire_missions(ninja, now=2800)), 1)
        self.assertEqual(ninja.active_missions, [])

    def test_request_checks_min_level_before_assignment(self):
        ninja = player(level=9)
        self.assertIn("at least level 10", missions.request_mission(ninja, "c"))
        self.assertEqual(ninja.active_missions, [])


if __name__ == "__main__":
    unittest.main()
