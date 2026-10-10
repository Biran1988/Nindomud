"""Combined maintenance accounting and active mastery checks."""

import unittest
from unittest.mock import patch

import upkeep_reports
from models import Player


class UpkeepReportTests(unittest.TestCase):
    def test_combined_report_is_due_after_six_minutes_even_after_source_stops(self):
        player = Player("Upkeeper", "Upkeeper")
        with patch.object(upkeep_reports.time, "monotonic", side_effect=[100, 120]):
            self.assertEqual(upkeep_reports.record(player, "Sharingan", 6), [])
            self.assertEqual(upkeep_reports.record(player, "Sage Mode", 12, 8), [])
        self.assertEqual(upkeep_reports.due(player, 459), [])
        self.assertEqual(upkeep_reports.due(player, 460), [
            "&CUpkeep total: Sharingan 6 Chakra; Sage Mode 12 Chakra, 8 Stamina (combined 18 Chakra, 8 Stamina).&x"
        ])
        self.assertEqual(upkeep_reports.due(player, 800), [])

    def test_turning_off_one_source_flushes_only_its_cost(self):
        player = Player("Upkeeper", "Upkeeper")
        with patch.object(upkeep_reports.time, "monotonic", side_effect=[100, 110]):
            upkeep_reports.record(player, "Samurai Sabre", 4)
            upkeep_reports.record(player, "Shadow Clones", 25)
        self.assertEqual(upkeep_reports.flush(player, "Samurai Sabre"), [
            "&CSamurai Sabre upkeep total: 4 Chakra.&x"
        ])
        self.assertEqual(upkeep_reports.due(player, 460), [
            "&CUpkeep total: Shadow Clones 25 Chakra (combined 25 Chakra).&x"
        ])

    def test_paid_maintenance_can_grow_skill_outside_combat(self):
        player = Player("Upkeeper", "Upkeeper")
        player.learned_skills.append("Samurai Sabre")
        player.skill_proficiencies["Samurai Sabre"] = 40
        with patch.object(upkeep_reports.time, "monotonic", side_effect=[0, 9, 10, 20, 21]), \
             patch.object(upkeep_reports.random, "randint", side_effect=[60, 61]):
            upkeep_reports.maintain_skill(player, "Samurai Sabre")
            upkeep_reports.maintain_skill(player, "Samurai Sabre")
            self.assertEqual(player.skill_proficiencies["Samurai Sabre"], 40)
            upkeep_reports.maintain_skill(player, "Samurai Sabre")
            self.assertEqual(player.skill_proficiencies["Samurai Sabre"], 41)
            upkeep_reports.maintain_skill(player, "Samurai Sabre")
            self.assertEqual(player.skill_proficiencies["Samurai Sabre"], 41)
            upkeep_reports.stop_maintaining(player, "Samurai Sabre")
            upkeep_reports.maintain_skill(player, "Samurai Sabre")
            self.assertEqual(player.skill_proficiencies["Samurai Sabre"], 41)
        player._immortal_skill_mastery = True
        upkeep_reports.maintain_skill(player, "Samurai Sabre")
        self.assertEqual(player.skill_proficiencies["Samurai Sabre"], 41)


if __name__ == "__main__":
    unittest.main()
