"""Each Mission-tagged NPC has exactly one level-relative mission rank."""
import unittest
from unittest.mock import patch

import combat
import missions
from models import Player


class SlidingMissionRanksTests(unittest.TestCase):
    def make_player(self, level):
        return Player("Ninja", "ninja", village="leaf", level=level)

    def test_same_mob_moves_s_a_b_c_d_as_player_levels(self):
        # All levels here are actual request-eligible levels for each rank.
        mob = {"short_desc": "a seasoned hunter", "level": 160,
               "act_flags": ["Npc", "Mission"]}
        with patch.object(combat, "MOB_TEMPLATES", {18160: mob}):
            for level, rank in [(80, "S-Rank"), (100, "A-Rank"),
                                (130, "B-Rank"), (150, "C-Rank"),
                                (155, "D-Rank"), (220, "D-Rank")]:
                with self.subTest(level=level, rank=rank):
                    ninja = self.make_player(level)
                    self.assertEqual(missions.mission_rank_for_levels(level, 160), rank)
                    found_vnum, chosen = missions.pick_mission_mob(ninja, rank)
                    self.assertEqual((found_vnum, chosen), (18160, mob))
                    request = missions.request_mission(ninja, rank)
                    self.assertIn("Mission requested", request)
                    self.assertEqual(ninja.active_missions[0]["dynamic"]["rank"], rank)
                    self.assertEqual(ninja.active_missions[0]["dynamic"]["target_mob_template"], 18160)

    def test_no_level_can_match_two_ranks_for_one_player(self):
        ranks = ["D-Rank", "C-Rank", "B-Rank", "A-Rank", "S-Rank"]
        for player_level in (1, 10, 25, 50, 80, 100, 150, 200, 240, 250):
            for mob_level in range(1, 251):
                classified = missions.mission_rank_for_levels(player_level, mob_level)
                matches = [
                    rank for rank in ranks
                    if missions.level_window_for_rank(player_level, rank)[0] <= mob_level
                    <= missions.level_window_for_rank(player_level, rank)[1]
                ]
                self.assertEqual(matches, [classified],
                                 (player_level, mob_level, matches))
        self.assertIsNone(missions.mission_rank_for_levels(80, 0))
        self.assertIsNone(missions.mission_rank_for_levels(80, 251))

    def test_weaker_enemies_never_fall_out_of_d_rank(self):
        for player_level in (1, 80, 150, 200, 250):
            for mob_level in (1, 20, 50, 80, 120, 160):
                if mob_level <= player_level:
                    self.assertEqual(missions.mission_rank_for_levels(player_level, mob_level),
                                     "D-Rank")

    def test_only_mission_tagged_mobs_and_exact_rank_eligible(self):
        templates = {
            1: {"short_desc": "weak", "level": 20, "act_flags": ["Mission"]},
            2: {"short_desc": "easy", "level": 105, "act_flags": ["Mission"]},
            3: {"short_desc": "medium", "level": 119, "act_flags": ["Mission"]},
            4: {"short_desc": "challenging", "level": 130, "act_flags": ["Mission"]},
            5: {"short_desc": "hard", "level": 155, "act_flags": ["Mission"]},
            6: {"short_desc": "extreme", "level": 210, "act_flags": ["Mission"]},
            7: {"short_desc": "unmarked", "level": 130, "act_flags": ["Npc"]},
            8: {"short_desc": "invalid", "level": 251, "act_flags": ["Mission"]},
        }
        expected = {"D-Rank": 1, "C-Rank": 3, "B-Rank": 4,
                    "A-Rank": 5, "S-Rank": 6}
        # Multiple D candidates are legal, but all must be in D's one band.
        with patch.object(combat, "MOB_TEMPLATES", templates):
            ninja = self.make_player(100)
            for rank in expected:
                with self.subTest(rank=rank):
                    vnum, template = missions.pick_mission_mob(ninja, rank)
                    self.assertIn("Mission", template["act_flags"])
                    self.assertEqual(missions.mission_rank_for_levels(100, template["level"]), rank)
                    self.assertNotIn(vnum, (7, 8))
            self.assertEqual(missions.pick_mission_mob(ninja, "X-Rank"), (None, None))

    def test_existing_active_mission_keeps_its_original_rank(self):
        mob = {"short_desc": "a veteran", "level": 160,
               "act_flags": ["Mission"]}
        with patch.object(combat, "MOB_TEMPLATES", {18160: mob}):
            ninja = self.make_player(80)
            response = missions.request_mission(ninja, "s")
            self.assertIn("Mission requested", response)
            ninja.level = 155
            self.assertEqual(missions.mission_rank_for_levels(ninja.level, 160), "D-Rank")
            self.assertEqual(ninja.active_missions[0]["dynamic"]["rank"], "S-Rank")
            self.assertIn("S-Rank", missions.mission_info(ninja))


if __name__ == "__main__":
    unittest.main()
