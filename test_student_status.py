"""Students are unranked; the first official ninja rank is earned at the Genin Exam."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import data_headbands
import genin_exam
import kage
import leveling
import programs
from models import Player


class StudentStatusTests(unittest.TestCase):
    def test_genin_is_first_official_rank_and_student_is_unranked(self):
        self.assertEqual(kage.RANK_ORDER[0], "genin")
        self.assertNotIn("student", kage.RANK_ORDER)
        self.assertNotIn("student", kage.RANK_LEVEL_CAPS)
        self.assertEqual(data_headbands.RANK_ORDER[0], "genin")
        student = Player("Aspirant", "Aspirant")
        self.assertEqual(student.village_rank, "student")
        self.assertEqual(leveling.rank_level_cap(student), 10)
        self.assertEqual(kage.RANK_LEVEL_CAPS["genin"], 15)

    def test_old_character_saves_are_upgraded_without_loss(self):
        saved = Player("Aspirant", "Aspirant", level=7, experience=216000,
                       village_rank="student", mission_points=12).to_dict()
        saved["village_rank"] = "academy student"
        migrated = Player.from_dict(saved)
        self.assertEqual(migrated.village_rank, "student")
        self.assertEqual((migrated.level, migrated.experience, migrated.mission_points),
                         (7, 216000, 12))

    def test_student_cannot_be_promoted_by_kage_or_mob_script(self):
        player = Player("Aspirant", "Aspirant", village="leaf", level=10)
        self.assertIn("Genin Exam", kage.handle_promotion_request(player))
        self.assertEqual(player.village_rank, "student")
        self.assertTrue(programs.validate_program("speech", "set_rank", "student",
                                                  {"speech"}, keyword="graduate"))
        session = NS(player=player, send=Mock())
        self.assertFalse(programs.run_action(session, "set_rank", "genin"))
        self.assertEqual(player.village_rank, "student")

    def test_real_genin_exam_accepts_student_after_mastery(self):
        player = Player("Aspirant", "Aspirant", level=10)
        player.learned_skills = list(genin_exam.STARTER_SKILLS)
        player.skill_proficiencies = {name: 100 for name in genin_exam.STARTER_SKILLS}
        session = NS(player=player, send=Mock(), iruka_exam=None,
                     combat_target=None, pvp_target=None, pending_cast=None,
                     controlled_clone=None)
        with patch.object(genin_exam, "iruka_here", return_value=object()):
            self.assertTrue(genin_exam.start_exam(session))
        self.assertEqual(player.village_rank, "student")
        self.assertIsNotNone(session.iruka_exam)


if __name__ == "__main__":
    unittest.main()
