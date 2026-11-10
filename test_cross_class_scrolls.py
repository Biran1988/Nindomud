"""Regression coverage for scroll-taught ordinary jutsu across combat classes."""
import unittest
from unittest.mock import patch

import combat
import commands
import data_jutsu
import olc
import skill_training
import storage
from models import Player
from session import Session, State


class CrossClassScrollTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.session = Session(self.messages.append, lambda: None)
        self.session.state = State.PLAYING
        self.session.account = type("Account", (), {"staff_level": "player"})()
        self.player = Player(
            "ScrollStudent", "ScrollStudent", level=60,
            primary_class="taijutsu", village="leaf", clan="nara")
        self.player.learned_skills = []
        self.player.practice_gate_enabled = True
        self.session.player = self.player
        self.scrolls = {
            "narakumi": "A Narakumi Scroll",
            "throw kunai": "A Throw Kunai Scroll",
            "rasengan": "A Rasengan Scroll",
            "chidori": "A Chidori Scroll",
            "weapon expert": "A Weapon Expert Scroll",
            "amaterasu": "An Amaterasu Scroll",
        }
        templates = {}
        for i, (key, name) in enumerate(self.scrolls.items()):
            templates[956000 + i] = dict(
                olc.default_object(956000 + i, name),
                item_type="scroll", scroll_jutsu=key)
        self.templates_patch = patch.object(olc, "OBJECT_TEMPLATES", templates)
        self.templates_patch.start()
        self.addCleanup(self.templates_patch.stop)
        self.saver_patch = patch.object(storage, "save_player")
        self.saved = self.saver_patch.start()
        self.addCleanup(self.saver_patch.stop)

    def learn(self, key):
        scroll = self.scrolls[key]
        self.player.inventory.append(scroll)
        commands.cmd_read(self.session, scroll.split())
        return scroll

    def test_taijutsu_student_can_learn_and_use_genjutsu_by_scroll(self):
        scroll = self.learn("narakumi")
        self.assertNotIn(scroll, self.player.inventory)
        self.assertIn("Narakumi", self.player.learned_skills)
        self.assertTrue(combat._can_use_jutsu(
            self.player, data_jutsu.JUTSU["narakumi"], "narakumi"))
        self.assertFalse(skill_training.needs_first_practice(self.player, "Narakumi"))
        self.saved.assert_called()
        self.assertEqual(self.player.primary_class, "taijutsu")
        self.assertNotIn("narakumi",
                         data_jutsu.jutsu_for_class_at_level("taijutsu", 15))
        catalog = "\n".join(commands.build_jutsu_catalog_lines(self.player))
        self.assertIn("Narakumi", catalog)
        self.assertIn("Cross-Class", catalog)

    def test_scroll_taught_bukijutsu_shows_in_prac_for_other_class(self):
        self.learn("throw kunai")
        commands.cmd_prac(self.session, [])
        output = "\n".join(self.messages)
        self.assertIn("Throw Kunai", output)
        self.assertIn("Bukijutsu", output)
        self.assertIn("Throw Kunai", self.player.learned_skills)

    def test_scroll_taught_ninjutsu_can_be_cast_by_taijutsu(self):
        self.learn("rasengan")
        self.assertTrue(combat._can_use_jutsu(
            self.player, data_jutsu.JUTSU["rasengan"], "rasengan"))
        self.assertNotIn("rasengan",
                         data_jutsu.jutsu_for_class_at_level("taijutsu", 25))

    def test_scroll_does_not_bypass_element_requirement(self):
        self.learn("chidori")
        self.assertIn("Chidori", self.player.learned_skills)
        self.assertFalse(combat._can_use_jutsu(
            self.player, data_jutsu.JUTSU["chidori"], "chidori"))
        self.player.chakra_nature = "lightning"
        self.assertTrue(combat._can_use_jutsu(
            self.player, data_jutsu.JUTSU["chidori"], "chidori"))

    def test_special_passive_cannot_be_cross_class_learned(self):
        scroll = self.learn("weapon expert")
        self.assertIn(scroll, self.player.inventory)
        self.assertNotIn("Weapon Expert", self.player.learned_skills)
        self.assertIn("cannot be learned by your class", "\n".join(self.messages))
        self.assertFalse(data_jutsu.scroll_can_cross_class(
            data_jutsu.JUTSU["weapon expert"]))

    def test_bloodline_jutsu_is_still_protected(self):
        scroll = self.learn("amaterasu")
        self.assertIn(scroll, self.player.inventory)
        self.assertNotIn("Amaterasu", self.player.learned_skills)
        self.assertFalse(data_jutsu.scroll_can_cross_class(
            data_jutsu.JUTSU["amaterasu"]))

    def test_scroll_is_not_consumed_when_already_known(self):
        self.learn("narakumi")
        scroll = self.learn("narakumi")
        self.assertIn(scroll, self.player.inventory)
        self.assertIn("already know Narakumi", "\n".join(self.messages))

    def test_own_class_special_scroll_still_uses_existing_rules(self):
        self.player.primary_class = "bukijutsu"
        scroll = self.learn("weapon expert")
        self.assertNotIn(scroll, self.player.inventory)
        self.assertIn("Weapon Expert", self.player.learned_skills)


if __name__ == "__main__":
    unittest.main()
