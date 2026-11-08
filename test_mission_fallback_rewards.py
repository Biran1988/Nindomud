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
        with patch.object(missions.time, "time", return_value=1000):
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

    def test_overlapping_reward_ranges_end_at_20(self):
        self.assertEqual(missions.MISSION_POINT_RANGES, {
            "D-Rank": (1, 5), "C-Rank": (4, 9), "B-Rank": (7, 13),
            "A-Rank": (11, 17), "S-Rank": (15, 20),
        })
        bands = list(missions.MISSION_POINT_RANGES.values())
        self.assertEqual(bands[-1][1], 20)
        for lower, higher in zip(bands, bands[1:]):
            self.assertLessEqual(higher[0], lower[1])

    def test_completion_rolls_once_in_each_rank_for_all_mission_types(self):
        p = ninja()
        expected_total = 0
        types = ("kill", "gather", "retrieve", "courier", "kill")
        with patch("village_perks.ryo_multiplier", return_value=1.0), \
                patch("village_perks.xp_multiplier", return_value=1.0), \
                patch("leveling.grant_experience", return_value=[]):
            for (rank, (minimum, maximum)), mission_type in zip(
                    missions.MISSION_POINT_RANGES.items(), types):
                for points in (minimum, maximum):
                    with self.subTest(rank=rank, type=mission_type, points=points):
                        entry = {"mission_id": f"dynamic_{rank}_{mission_type}_{points}",
                                 "progress": 1}
                        mission = {
                            "mission_id": entry["mission_id"],
                            "mission_type": mission_type,
                            "rank": rank, "title": "Test mission", "target_count": 1,
                            "reward_xp": 0, "reward_ryo": 10,
                            "reward_mission_points": 999, "cooldown_seconds": 60,
                        }
                        p.active_missions.append(entry)
                        with patch.object(missions.random, "randint", return_value=points) as roll:
                            messages = missions._complete_mission(p, mission, entry)
                        roll.assert_called_once_with(minimum, maximum)
                        self.assertIn(f"and {points} mission point(s).", messages[0])
                        expected_total += points
                        self.assertEqual(p.mission_points, expected_total)
                        self.assertEqual(p.mission_points_earned_total, expected_total)
        self.assertEqual(len(p.completed_missions), 10)

    def test_mission_info_shows_its_rank_reward_band(self):
        p = ninja()
        p.active_missions.append({
            "mission_id": "dynamic_S-Rank_info",
            "progress": 0,
            "expires_at": missions.time.time() + 100,
            "dynamic": {
                "mission_id": "dynamic_S-Rank_info", "rank": "S-Rank",
                "mission_type": "retrieve", "title": "Find the scroll",
                "target_count": 1, "quest_item_name": "Lost scroll",
                "quest_region": "Roadside Inn",
            },
        })
        self.assertIn("15-20 (random)", missions.mission_info(p))


if __name__ == "__main__":
    unittest.main()
