"""Regression tests for Iruka VNUM 11's randomized, mastery-gated exam."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import combat
import genin_exam
import kage
import programs
import storage
import world
from models import Player


class IrukaGraduationTests(unittest.TestCase):
    def setUp(self):
        for target, attribute in (
            (combat, "MOB_TEMPLATES"),
            (combat, "MOBS_BY_ROOM"),
            (world.WORLD, "rooms"),
        ):
            p = patch.object(target, attribute, {})
            p.start()
            self.addCleanup(p.stop)
        world.WORLD.add_room(world.Room(30, "Academy Class", "The exam classroom."))
        world.WORLD.add_room(world.Room(31, "Hallway", "Outside the exam room."))
        combat.register_template(11, "Iruka Umino", 25, 100, 3, 9, 0, 0)
        combat.register_template(12, "Other teacher", 25, 100, 3, 9, 0, 0)
        self.iruka = combat.spawn_mob(11, 30)
        self.fake_teacher = combat.spawn_mob(12, 30)
        self.player = Player("Aspirant", "Aspirant", room_vnum=30)
        self.player.level = 10
        self.player.village_rank = "academy student"
        self.player.learned_skills = list(genin_exam.STARTER_SKILLS)
        self.player.skill_proficiencies = {name: 100 for name in genin_exam.STARTER_SKILLS}
        self.session = NS(player=self.player, send=Mock(), broadcast_room=Mock(),
                          combat_target=None, pvp_target=None, pending_cast=None,
                          controlled_clone=None, iruka_exam=None)
        self.session.active_sessions = lambda: [self.session]
        for module, func in ((kage, "announce_rank_up"),
                             (storage, "save_player")):
            p = patch.object(module, func)
            p.start()
            self.addCleanup(p.stop)

    def _start(self):
        self.assertTrue(genin_exam.start_exam(self.session))
        return self.session.iruka_exam

    def test_bank_has_exactly_20_distinct_questions_with_four_unique_answers(self):
        self.assertEqual(len(genin_exam.QUESTION_BANK), 20)
        self.assertEqual(len({row[0] for row in genin_exam.QUESTION_BANK}), 20)
        for entry in genin_exam.QUESTION_BANK:
            self.assertEqual(len(entry), 5)
            self.assertEqual(len(set(entry[1:])), 4)
        self.assertEqual(len(genin_exam.STARTER_SKILLS), 5)
        self.assertIn("Strong Fist Style", genin_exam.STARTER_SKILLS)

    def test_mastery_level_and_rank_are_mandatory(self):
        self.player.level = 9
        self.assertFalse(genin_exam.start_exam(self.session))
        self.player.level = 10
        for skill in genin_exam.STARTER_SKILLS:
            self.player.skill_proficiencies[skill] = 99
            self.assertFalse(genin_exam.start_exam(self.session))
            self.assertIsNone(self.session.iruka_exam)
            self.player.skill_proficiencies[skill] = 100
        self.player.learned_skills.remove("Strong Fist Style")
        self.assertFalse(genin_exam.start_exam(self.session))
        self.player.learned_skills.append("Strong Fist Style")
        self.player.village_rank = "genin"
        self.assertFalse(genin_exam.start_exam(self.session))

    def test_only_real_iruka_vnum11_in_same_room_can_start_or_continue(self):
        self.player.room_vnum = 31
        self.assertFalse(genin_exam.start_exam(self.session))
        self.player.room_vnum = 30
        exam = self._start()
        self.player.room_vnum = 31
        self.assertTrue(genin_exam.handle_answer(self.session, "a"))
        self.assertIsNone(self.session.iruka_exam)
        self.player.room_vnum = 30
        combat.remove_mob(self.iruka)
        self.assertFalse(genin_exam.start_exam(self.session))

    def test_only_exact_spoken_start_genin_exam_starts_and_blocks_movement(self):
        commands.cmd_ask(self.session, ["iruka", "about", "graduation"])
        self.assertIsNone(self.session.iruka_exam)
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_say(self.session, ["Start", "Genin", "exam"])
        self.assertIsNotNone(self.session.iruka_exam)
        position = self.session.iruka_exam["index"]
        self.assertTrue(genin_exam.handle_answer(self.session, "north"))
        self.assertEqual(position, self.session.iruka_exam["index"])
        self.assertTrue(genin_exam.handle_answer(self.session, "cancel"))
        self.assertIsNone(self.session.iruka_exam)

    def test_spoken_exam_phrase_requires_iruka_and_is_case_insensitive(self):
        combat.remove_mob(self.iruka)
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_say(self.session, ["sTaRt", "GeNiN", "ExAm"])
        self.assertIsNone(self.session.iruka_exam)
        self.iruka = combat.spawn_mob(11, 30)
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_say(self.session, ["START", "GENIN", "EXAM"])
        self.assertIsNotNone(self.session.iruka_exam)

    def test_per_attempt_random_ten_questions_and_shuffled_option_positions(self):
        first = self._start()
        first_question_texts = [x[0] for x in first["paper"]]
        first_answer_positions = [x[2] for x in first["paper"]]
        self.assertEqual(len(first_question_texts), 10)
        self.assertEqual(len(set(first_question_texts)), 10)
        self.assertTrue(all(0 <= n < 4 for n in first_answer_positions))
        for question, options, answer_index in first["paper"]:
            original = next(item for item in genin_exam.QUESTION_BANK if item[0] == question)
            self.assertEqual(options[answer_index], original[1])
            self.assertEqual(set(options), set(original[1:]))
        genin_exam.handle_answer(self.session, "cancel")
        second = self._start()
        second_question_texts = [x[0] for x in second["paper"]]
        self.assertNotEqual(set(first_question_texts), set(second_question_texts))

    def test_wrong_answer_fails_without_graduating_or_reward(self):
        quiz = self._start()
        wrong = (quiz["paper"][0][2] + 1) % 4
        self.assertTrue(genin_exam.handle_answer(self.session, "ABCD"[wrong]))
        self.assertEqual(self.player.village_rank, "academy student")
        self.assertIsNone(self.session.iruka_exam)

    def test_all_ten_answers_required_to_graduate_and_reward_once(self):
        quiz = self._start()
        with patch("data_headbands.apply_rank_headband") as headband:
            for index in range(10):
                state = self.session.iruka_exam
                answer = state["paper"][index][2]
                genin_exam.handle_answer(self.session, f"answer {'ABCD'[answer]}")
                if index < 9:
                    self.assertEqual(self.player.village_rank, "academy student")
            self.assertEqual(self.player.village_rank, "genin")
            self.assertEqual(self.player.mission_points, 50)
            self.assertIsNone(self.session.iruka_exam)
            headband.assert_called_once_with(self.player, "genin")
            kage.announce_rank_up.assert_called_once_with("Aspirant", "genin")
            storage.save_player.assert_called_once_with(self.player)
            self.assertFalse(genin_exam.start_exam(self.session))
            self.assertEqual(self.player.mission_points, 50)

    def test_iruka_legacy_graduation_program_no_longer_starts_exam(self):
        action = {"trigger": "speech", "keyword": "graduate",
                  "action": "iruka_graduation_check", "args": ""}
        template = combat.MOB_TEMPLATES[11]
        template["mob_programs"] = [action]
        self.assertTrue(programs.fire_speech_programs(
            self.session, template["mob_programs"], "graduate",
            speaker_name=self.iruka.name, mob_template=template, mob=self.iruka))
        self.assertIsNone(self.session.iruka_exam)
        self.assertEqual(self.player.village_rank, "academy student")
        self.assertFalse(programs.run_action(
            self.session, "iruka_graduation_check", "", mob=self.fake_teacher))
        self.assertIsNone(self.session.iruka_exam)

    def test_generic_set_rank_program_cannot_bypass_iruka(self):
        self.assertFalse(programs.run_action(self.session, "set_rank", "genin"))
        self.assertEqual(self.player.village_rank, "academy student")
        self.assertIsNone(self.session.iruka_exam)


if __name__ == "__main__":
    unittest.main()
