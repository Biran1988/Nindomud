"""Mangekyo betrayal must not erase practiced skill mastery."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import commands
from models import Player


class MangekyoSacrificeFloorTests(unittest.TestCase):
    def test_practiced_and_earned_mastery_have_one_percent_floor(self):
        attacker = Player("Caster", "Caster")
        victim = Player("Victim", "Victim", health=100, maximum_health=500)
        victim.downed_by = attacker.name
        victim.experience = 400
        victim.ryo = 800
        victim.skill_proficiencies = {
            "Barely Practiced": 1,
            "Low Practiced": 2,
            "Previously Practiced At Zero": 0,
            "Practiced At 80": 80,
            "Learned But Unpracticed": 0,
            "Special Grant With Progress": 1,
            "Maxed Signature": 150,
        }
        victim.practiced_skills = [
            "Barely Practiced", "Low Practiced",
            "Previously Practiced At Zero", "Practiced At 80",
            "Maxed Signature",
        ]
        caster_session = SimpleNamespace(player=attacker, send=Mock(), connection_ip='192.0.2.1')
        victim_session = SimpleNamespace(player=victim, send=Mock(), send_prompt=Mock(), connection_ip='192.0.2.2')

        with patch("session.ACTIVE_SESSIONS", [caster_session, victim_session]), \
             patch("data_mangekyo.roll_two_eye_techniques",
                   return_value=("amaterasu", "kamui")), \
             patch("commands.time.time", return_value=123456.0):
            commands.cmd_finish_downed_yes(caster_session, [])

        self.assertEqual(victim.skill_proficiencies, {
            "Barely Practiced": 1,
            "Low Practiced": 1,
            "Previously Practiced At Zero": 1,
            "Practiced At 80": 60,
            "Learned But Unpracticed": 0,
            "Special Grant With Progress": 1,
            "Maxed Signature": 112,
        })
        self.assertEqual(victim.experience, 300)
        self.assertEqual(victim.ryo, 400)
        self.assertEqual(victim.health, 1)
        self.assertEqual(victim.maximum_health, 500)
        self.assertEqual(victim.frozen_until, 123456.0 + 24 * 60 * 60)
        self.assertIsNone(victim.downed_by)
        self.assertTrue(attacker.bloodline_mangekyo)
        self.assertEqual((attacker.mangekyo_eye_1, attacker.mangekyo_eye_2),
                         ("amaterasu", "kamui"))


if __name__ == "__main__":
    unittest.main()
