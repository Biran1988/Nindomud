"""Regression tests for the gameplay changes requested after Kamui pocket closure."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import chunin_exam
import combat
import player_teaching
import sage_mode
import skill_training
from models import Player


class October30DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.teacher = Player('SenseiTest', 'SenseiTest', village='leaf', clan='nara')
        self.student = Player('PupilTest', 'PupilTest', village='leaf', clan='nara')
        for p in (self.teacher, self.student):
            p.primary_class = 'taijutsu'
            p.room_vnum = 111111
            p.level = 100
            p.learned_skills = ['Dynamic Entry', 'Chakra Charge']
            p.practice_gate_enabled = True
            p.skill_proficiencies = {'Dynamic Entry': 0, 'Chakra Charge': 0}
        self.teacher.skill_proficiencies['Chakra Charge'] = 100
        self.student.practice_points = 4
        self.teacher_session = NS(player=self.teacher, send=Mock(), combat_target=None,
                                  pvp_target=None, broadcast_room=Mock())
        self.student_session = NS(player=self.student, send=Mock(), combat_target=None,
                                  pvp_target=None)
        self.teacher_session.active_sessions = lambda: [self.teacher_session, self.student_session]

    def test_teach_reaches_45_without_practice_and_exempts_first_gate(self):
        with patch('player_teaching.storage.save_player') as saved, \
             patch('room_actions.emit'):
            player_teaching.command(self.teacher_session, ['pupiltest', 'chakra', 'charge'])
        self.assertEqual(self.student.skill_proficiencies['Chakra Charge'], 45)
        self.assertEqual(self.student.practice_points, 4)
        self.assertTrue('Chakra Charge' in self.student.practiced_skills)
        self.assertFalse(skill_training.needs_first_practice(self.student, 'Chakra Charge'))
        saved.assert_called_once_with(self.student)

    def test_teach_rejects_unmastered_other_class_or_student_above_five(self):
        with patch('player_teaching.storage.save_player') as save:
            self.teacher.skill_proficiencies['Chakra Charge'] = 99
            player_teaching.command(self.teacher_session, ['pupiltest', 'chakra', 'charge'])
            self.teacher.skill_proficiencies['Chakra Charge'] = 100
            self.student.primary_class = 'ninjutsu'
            player_teaching.command(self.teacher_session, ['pupiltest', 'chakra', 'charge'])
            self.student.primary_class = 'taijutsu'
            self.student.skill_proficiencies['Chakra Charge'] = 6
            player_teaching.command(self.teacher_session, ['pupiltest', 'chakra', 'charge'])
            save.assert_not_called()
        self.assertEqual(self.student.skill_proficiencies['Chakra Charge'], 6)

    def test_scrolls_in_bags_count_for_final_and_pvp_theft(self):
        p = self.student
        p.inventory = [chunin_exam.HEAVEN_SCROLL]
        p.backpack_contents = {'0': [chunin_exam.EARTH_SCROLL]}
        self.assertTrue(chunin_exam.has_both_scrolls(p))
        self.assertTrue(chunin_exam.consume_both_scrolls(p))
        self.assertFalse(chunin_exam.has_both_scrolls(p))
        p.in_chunin_exam = self.teacher.in_chunin_exam = True
        p.backpack_contents['0'] = [chunin_exam.EARTH_SCROLL]
        self.teacher.inventory = [chunin_exam.HEAVEN_SCROLL]
        stolen = chunin_exam.steal_scroll_on_pvp_defeat(self.teacher, p)
        self.assertEqual(stolen, chunin_exam.EARTH_SCROLL)
        self.assertFalse(p.backpack_contents['0'])
        self.assertTrue(chunin_exam.has_both_scrolls(self.teacher))
        chunin_exam.reset_exam(self.teacher)
        self.assertFalse(chunin_exam.has_both_scrolls(self.teacher))

    def test_toad_stomach_is_not_a_mob_and_devours_with_chakra_upkeep(self):
        player = self.teacher
        player.level = 90
        player.chakra = 400
        player.signed_summoning_contracts = ['toad']
        combat.register_template(98919, 'a trapped examinee', level=20,
                                 max_health=500, min_damage=5, max_damage=7, experience_reward=0, ryo_reward=0)
        target = combat.spawn_mob(98919, player.room_vnum)
        self.assertIsNotNone(target)
        orig_chakra = player.chakra
        try:
            with patch('room_actions.emit'):
                sage_mode.summon_command(self.teacher_session, ['toad', 'stomach', 'trapped'])
            trap = combat.active_summon(player)
            self.assertTrue(getattr(trap, 'is_toad_stomach_barrier', False))
            self.assertNotIn(trap, combat.mobs_in_room(player.room_vnum))
            self.assertIs(combat.toad_stomach_target(target), trap)
            before = target.health
            combat.tick_summon_upkeep(self.teacher_session)
            self.assertLess(target.health, before)
            self.assertLess(player.chakra, orig_chakra)
            self.assertTrue(target.summon_trap_applied)
            self.assertGreater(target.summon_trap_to_hit_penalty, 0)
            combat.dismiss_summon(player)
            self.assertIsNone(combat.toad_stomach_target(target))
            self.assertEqual(target.summon_trap_to_hit_penalty, 0)
        finally:
            combat.dismiss_summon(player)
            combat.remove_mob(target)

    def test_contract_cannot_be_signed_outside_real_elder(self):
        self.teacher.signed_summoning_contracts = []
        self.teacher.level = 90
        sage_mode.sign_command(self.teacher_session, ['salamander'])
        self.assertFalse(self.teacher.signed_summoning_contracts)


if __name__ == '__main__':
    unittest.main()
