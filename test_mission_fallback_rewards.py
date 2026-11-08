"""No-mob mission fallback and randomized mission-point reward regressions."""
import unittest
from unittest.mock import patch

import missions
from models import Player


def ninja():
    return Player("Fallback", "fallback", village="leaf", level=60)


class MissionFallbackRewardsTests(unittest.TestCase):
    def test_no_hunt_tries_recovery_then_delivery(self):
        p = ninja()
        def courier_success(player, rank):
            player.active_missions.append({
                "mission_id": "dynamic_" + rank + "_courier_test",
                "progress": 0,
                "dynamic": {"mission_id": "dynamic_" + rank + "_courier_test",
                            "rank": rank, "mission_type": "courier",
                            "title": "Courier", "target_count": 1},
            })
            return "Mission requested: Courier"
        with patch.object(missions, "pick_mission_mob", return_value=(None, None)), \
                patch.object(missions.random, "shuffle", side_effect=lambda options: None), \
                patch.object(missions, "request_item_mission",
                             return_value="No eligible roads") as recovery, \
                patch.object(missions, "request_courier_mission",
                             side_effect=courier_success) as courier, \
                patch.object(missions.time, "time", return_value=1000):
            result = missions.request_mission(p, "b")
        self.assertTrue(result.startswith("Mission requested:"), result)
        self.assertIn("noncombat", result)
        recovery.assert_called_once_with(p, "B-Rank")
        courier.assert_called_once_with(p, "B-Rank")
        self.assertEqual(p.active_missions[0]["dynamic"]["mission_type"], "courier")
        self.assertEqual(p.mission_cooldowns["dynamic_B-Rank"], 2200)
        self.assertIn("too recently", missions.request_mission(p, "b"))

    def test_no_hunt_can_choose_recovery_first(self):
        p = ninja()
        with patch.object(missions, "pick_mission_mob", return_value=(None, None)), \
                patch.object(missions.random, "shuffle", side_effect=lambda options: None), \
                patch.object(missions, "request_item_mission",
                             return_value="Mission requested: Recovery") as recovery, \
                patch.object(missions, "request_courier_mission") as courier:
            result = missions.request_mission(p, "c")
        self.assertTrue(result.startswith("Mission requested:"))
        recovery.assert_called_once_with(p, "C-Rank")
        courier.assert_not_called()

    def test_no_fallback_available_uses_no_hunt_request_cooldown(self):
        p = ninja()
        with patch.object(missions, "pick_mission_mob", return_value=(None, None)), \
                patch.object(missions, "request_item_mission", return_value="No roads"), \
                patch.object(missions, "request_courier_mission", return_value="No NPCs"):
            result = missions.request_mission(p, "a")
        self.assertIn("No suitable Mission-flagged enemy or noncombat fallback", result)
        self.assertEqual(p.active_missions, [])
        self.assertNotIn("dynamic_A-Rank", p.mission_cooldowns)

    def test_completion_rolls_once_per_mission_from_1_to_5(self):
        p = ninja()
        with patch("village_perks.ryo_multiplier", return_value=1.0), \
                patch("village_perks.xp_multiplier", return_value=1.0), \
                patch("leveling.grant_experience", return_value=[]):
            for points in (1, 5):
                entry = {"mission_id": "dynamic_C-Rank_test_" + str(points),
                         "progress": 1}
                mission = {
                    "mission_id": entry["mission_id"], "mission_type": "retrieve",
                    "rank": "C-Rank", "title": "Sample Recovery",
                    "target_count": 1, "reward_xp": 0, "reward_ryo": 10,
                    "reward_mission_points": 999, "cooldown_seconds": 60,
                }
                p.active_missions.append(entry)
                with patch.object(missions.random, "randint", return_value=points) as roll:
                    messages = missions._complete_mission(p, mission, entry)
                roll.assert_called_once_with(1, 5)
                self.assertIn(f"and {points} mission point(s).", messages[0])
        self.assertEqual(p.mission_points, 6)
        self.assertEqual(p.mission_points_earned_total, 6)
        self.assertEqual(len(p.completed_missions), 2)


if __name__ == "__main__":
    unittest.main()
