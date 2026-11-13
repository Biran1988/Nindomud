"""Iron Kage return and fourth-attack first lesson regression checks."""
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import commands
import combat
import help_system
import iron_ascension
from models import Player


class TowerResetAndFourthPracticeTests(unittest.TestCase):
    def test_final_floor_transfer_requires_correct_kill_and_preserves_reward(self):
        player = Player('Verifier', 'Verifier', level=250)
        player.room_vnum = iron_ascension.START + 249
        player.iron_ascension_completed = True
        session = NS(player=player, send=Mock())
        wrong = NS(room_vnum=player.room_vnum,
                   template_vnum=iron_ascension.guardian_vnum(249))
        self.assertFalse(iron_ascension.defeated(session, wrong))
        final = NS(room_vnum=player.room_vnum,
                   template_vnum=iron_ascension.guardian_vnum(250))
        with patch('storage.save_player'), patch('world.WORLD.get', return_value=object()), \\
             patch('commands.cmd_look'):
            self.assertTrue(iron_ascension.defeated(session, final))
        self.assertEqual(player.room_vnum, iron_ascension.START)
        self.assertFalse(iron_ascension.defeated(session, final))
        self.assertEqual(player.mission_points, 0)

    def test_fourth_practice_from_non_buki_teacher_at_level_75(self):
        player = Player('Verifier', 'Verifier', primary_class='bukijutsu', level=75, room_vnum=444)
        player.learned_skills = ['Fourth Attack']
        player.practice_points = 1
        player.practice_gate_enabled = True
        session = NS(player=player, send=Mock())
        teacher = NS(template_vnum=123456)
        with patch.object(combat, 'mobs_in_room', return_value=[teacher]), \
             patch.dict(combat.MOB_TEMPLATES, {123456: {'teacher': 'ninjutsu'}}):
            commands.cmd_prac(session, ['fourth', 'attack'])
        self.assertIn('Fourth Attack', player.practiced_skills)
        self.assertGreater(player.skill_proficiencies['Fourth Attack'], 0)
        self.assertEqual(player.practice_points, 0)

    def test_all_sword_help_pages_exist(self):
        import sword_styles
        with tempfile.TemporaryDirectory() as folder, patch.object(help_system, 'HELP_DIR', folder):
            help_system.seed_default_help()
            for name in sword_styles.STYLES:
                self.assertEqual(help_system.find_by_keyword(name)['primary_keyword'], name.lower())


if __name__ == '__main__':
    unittest.main()
