"""First teacher practice, special grants, and legacy-save migration."""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import combat
import data_jutsu
import skill_training
import storage
from models import Player
from session import ACTIVE_SESSIONS, Session, State


class FirstPracticeGateTests(unittest.TestCase):
    def setUp(self):
        self.p = Player("NewNinja", "NewNinja", village="leaf", clan="nara")
        self.p.practice_gate_enabled = True
        self.p.learned_skills = ["Dynamic Entry", "Sword", "Strong Fist Style",
                                 "Scan", "Chakra Charge", "Examine"]
        self.p.skill_proficiencies = {name: 0 for name in self.p.learned_skills}
        self.p.practice_points = 3
        self.s = NS(player=self.p, send=Mock(), account=NS(staff_level="player"),
                    combat_target=None, pvp_target=None, active_sessions=lambda: [])

    def test_normal_jutsu_blocked_until_practiced(self):
        commands.cmd_use_jutsu(self.s, "dynamic entry", ["enemy"])
        self.assertIn("Practice Dynamic Entry", self.s.send.call_args.args[0])
        self.assertFalse(combat._can_use_jutsu(self.p, data_jutsu.JUTSU["dynamic entry"],
                                                "dynamic entry"))

    def test_paid_teacher_lesson_permanently_unlocks(self):
        with patch.object(commands, "_find_matching_teacher", return_value=object()):
            commands.cmd_practice(self.s, ["dynamic", "entry"])
        self.assertIn("Dynamic Entry", self.p.practiced_skills)
        self.assertFalse(skill_training.needs_first_practice(self.p, "Dynamic Entry"))
        self.p.skill_proficiencies["Dynamic Entry"] = 0
        self.assertFalse(skill_training.needs_first_practice(self.p, "Dynamic Entry"))

    def test_weapon_growth_requires_first_practice(self):
        with patch.object(combat.random, "randint", return_value=1):
            combat.grow_skill_from_usage(self.p, "Sword", session=self.s)
        self.assertEqual(self.p.skill_proficiencies["Sword"], 0)
        skill_training.mark_practiced(self.p, "Sword")
        with patch.object(combat.random, "randint", return_value=1):
            combat.grow_skill_from_usage(self.p, "Sword", session=self.s)
        self.assertEqual(self.p.skill_proficiencies["Sword"], 2)

    def test_passives_scroll_and_special_grants_exempt(self):
        self.assertFalse(skill_training.needs_first_practice(self.p, "Strong Fist Style"))
        skill_training.grant_without_practice(self.p, "Dynamic Entry")
        self.assertFalse(skill_training.needs_first_practice(self.p, "Dynamic Entry"))
        self.assertTrue(skill_training.needs_first_practice(self.p, "Sword"))
        self.p.learned_skills.append("1000 Years of Death")
        self.assertFalse(skill_training.needs_first_practice(self.p, "1000 Years of Death"))

    def test_utility_skills_require_practice(self):
        self.p.level = 30
        commands.cmd_scan(self.s, ["north"])
        self.assertIn("Practice Scan", self.s.send.call_args.args[0])
        commands.cmd_charge(self.s, ["10"])
        self.assertIn("Practice Chakra Charge", self.s.send.call_args.args[0])
        self.p.inventory = ["Training Kunai"]
        commands.cmd_examine(self.s, ["kunai"])
        self.assertIn("Practice Examine", self.s.send.call_args.args[0])

    def test_authenticated_immortal_utility_skills_skip_first_lesson(self):
        session = Session(lambda text: None, lambda: None)
        self.addCleanup(ACTIVE_SESSIONS.remove, session)
        session.player = self.p
        session.account = NS(staff_level="helper")
        session.state = State.PLAYING
        self.p.chakra = 0
        self.p.stamina = 100
        commands.cmd_charge(session, ["10"])
        self.assertIsNotNone(session.chakra_charge)
        for name in self.p.learned_skills:
            self.assertFalse(skill_training.needs_first_practice(self.p, name))
        self.assertEqual(self.p.practiced_skills, [])
        session.account = None
        self.assertTrue(skill_training.needs_first_practice(self.p, "Chakra Charge"))

    def test_legacy_save_positive_proficiency_grandfathered(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(storage, "DATA_DIR", folder), \
                 patch.object(storage, "PLAYERS_DIR", os.path.join(folder, "players")), \
                 patch.object(storage, "ACCOUNTS_DIR", os.path.join(folder, "accounts")):
                storage.ensure_dirs()
                old = self.p.to_dict()
                for key in ("practice_gate_enabled", "practiced_skills", "practice_exempt_skills"):
                    old.pop(key)
                old["skill_proficiencies"]["Sword"] = 7
                with open(storage.player_path(self.p.name), "w", encoding="utf8") as file:
                    json.dump(old, file)
                loaded = storage.load_player(self.p.name)
                self.assertTrue(loaded.practice_gate_enabled)
                self.assertIn("Sword", loaded.practiced_skills)
                self.assertTrue(skill_training.needs_first_practice(loaded, "Dynamic Entry"))
                self.assertFalse(skill_training.needs_first_practice(loaded, "Sword"))
                self.assertIn("Sword", storage.load_player(self.p.name).practiced_skills)


if __name__ == "__main__":
    unittest.main()
