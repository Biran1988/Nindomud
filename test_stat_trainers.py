"""SWR-style NPC stat training: timed success, failure and location gates."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import config
from models import Player


class TimedStatTrainingTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Shinobi", "Account", room_vnum=1)
        self.player.training_points = 4
        self.trainer = NS(name="an academy instructor", health=100, template_vnum=6009)
        self.session = NS(player=self.player, send=Mock(), combat_target=None,
                          pvp_target=None, pending_cast=None, is_busy=lambda: False)
        self.session.start_timed_action = Mock()

    def _start(self, stat="cc"):
        with patch.object(combat, "mobs_in_room", return_value=[self.trainer]), \
             patch.object(combat, "is_stat_trainer", return_value=True):
            commands.cmd_train(self.session, [stat])

    def _finish(self, roll=1, present=True):
        callback = self.session.start_timed_action.call_args.args[2]
        with patch.object(combat, "mobs_in_room",
                          return_value=[self.trainer] if present else []), \
             patch.object(combat, "is_stat_trainer", return_value=True), \
             patch.object(commands.random, "randint", return_value=roll):
            callback()

    def test_requires_real_trainer(self):
        with patch.object(combat, "mobs_in_room", return_value=[]):
            commands.cmd_train(self.session, ["cc"])
        self.session.start_timed_action.assert_not_called()
        self.assertEqual(self.player.chakra_control, 10)

    def test_15_seconds_no_instant_gain(self):
        self._start()
        self.assertEqual(self.session.start_timed_action.call_args.args[1], 15)
        self.assertEqual(self.player.chakra_control, 10)
        self.assertEqual(self.player.training_points, 4)
        self._finish(1)
        self.assertEqual(self.player.chakra_control, 11)
        self.assertEqual(self.player.maximum_chakra, 85)
        self.assertEqual(self.player.training_points, 3)

    def test_failure_consumes_no_point(self):
        self._start("str")
        self._finish(100)
        self.assertEqual(self.player.strength, 10)
        self.assertEqual(self.player.training_points, 4)

    def test_leaving_or_losing_trainer_interrupts(self):
        self._start("wis")
        self.player.room_vnum = 2
        self._finish()
        self.assertEqual(self.player.wisdom, 10)
        self.player.room_vnum = 1
        self.session.start_timed_action.reset_mock()
        self._start("wis")
        self._finish(present=False)
        self.assertEqual(self.player.wisdom, 10)
        self.assertEqual(self.player.training_points, 4)

    def test_combat_interrupts_and_max_stat_blocks(self):
        self._start("per")
        self.session.combat_target = object()
        self._finish()
        self.assertEqual(self.player.perception, 10)
        self.session.start_timed_action.reset_mock()
        self.session.combat_target = None
        self.player.perception = config.MAX_ATTRIBUTE_VALUE
        self._start("per")
        self.session.start_timed_action.assert_not_called()

    def test_trainer_flag_is_distinct_from_jutsu_teacher(self):
        mob = NS(template_vnum=987650)
        with patch.dict(combat.MOB_TEMPLATES, {987650: {"act_flags": ["Trainer"], "teacher": ""}}):
            self.assertTrue(combat.is_stat_trainer(mob))
            self.assertFalse(combat.is_teacher(mob))
            self.assertTrue(combat.is_immortal_mob(mob))


if __name__ == "__main__":
    unittest.main()
