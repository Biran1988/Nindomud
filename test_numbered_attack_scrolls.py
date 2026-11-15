"""Scroll-only numbered attacks, migration-safe unlocks and saved mastery."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import combat
import commands
import data_jutsu
import jutsu_scroll_catalog as catalog
import leveling
import olc
import storage
from models import Player


class NumberedAttackScrollTests(unittest.TestCase):
    def setUp(self):
        self.templates = patch.object(olc, "OBJECT_TEMPLATES", {})
        self.templates.start()
        self.addCleanup(self.templates.stop)
        self.save = patch.object(storage, "save_player")
        self.saved = self.save.start()
        self.addCleanup(self.save.stop)
        catalog.install(migrate_saved=False)

    def player_and_session(self, ninja_class="bukijutsu", level=250):
        player = Player("ScrollFighter", "ScrollFighter",
                        primary_class=ninja_class, level=level)
        messages = []
        return player, NS(player=player, send=messages.append), messages

    def read(self, session, name):
        scroll = catalog.name_for(name)
        session.player.inventory.append(scroll)
        commands.cmd_read(session, scroll.split())
        return scroll

    def test_new_and_returning_players_need_scrolls(self):
        for ninja_class in ("bukijutsu", "ninjutsu", "taijutsu", "genjutsu"):
            with self.subTest(ninja_class=ninja_class):
                p, _, _ = self.player_and_session(ninja_class)
                with patch.object(leveling.shinobi_notices, "announce_level"):
                    leveling.sync_universal_skills(p)
                self.assertFalse(set(p.learned_skills) & {
                    "Second Attack", "Third Attack", "Fourth Attack", "Fifth Attack"})
                self.assertIn("Handsigns", p.learned_skills)

    def test_scrolls_have_stable_vnums_and_level_class_restrictions(self):
        expected = {"second attack": (31740, 25, "general"),
                    "third attack": (31741, 50, "bukijutsu"),
                    "fourth attack": (31742, 75, "bukijutsu"),
                    "fifth attack": (31743, 90, "bukijutsu")}
        for name, (vnum, level, klass) in expected.items():
            self.assertEqual(catalog.vnum_for(name), vnum)
            self.assertEqual(data_jutsu.MULTI_ATTACK_SCROLLS[name]["level_requirement"], level)
            self.assertEqual(data_jutsu.MULTI_ATTACK_SCROLLS[name]["class_requirement"], klass)
            self.assertEqual(olc.OBJECT_TEMPLATES[vnum]["scroll_jutsu"], name)

    def test_eligible_bukijutsu_reads_all_four_skills(self):
        p, session, messages = self.player_and_session()
        for name in ("second attack", "third attack", "fourth attack", "fifth attack"):
            with self.subTest(name=name):
                scroll = self.read(session, name)
                self.assertNotIn(scroll, p.inventory)
                self.assertIn(name.title(), p.learned_skills)
                self.assertEqual(p.skill_proficiencies[name.title()], 0)
                self.assertIn("learned", messages[-1])
        with patch.object(combat.random, "randint", return_value=1):
            self.assertEqual(combat._roll_extra_attacks(p), 0)

    def test_below_level_and_wrong_class_do_not_consume_scroll(self):
        for name, level in (("second attack", 24), ("third attack", 49),
                            ("fourth attack", 74), ("fifth attack", 89)):
            p, session, _ = self.player_and_session(level=level)
            scroll = self.read(session, name)
            self.assertIn(scroll, p.inventory)
            self.assertNotIn(name.title(), p.learned_skills)
        p, session, _ = self.player_and_session("ninjutsu", level=99)
        scroll = self.read(session, "second attack")
        self.assertIn(scroll, p.inventory)
        p.level = 100
        commands.cmd_read(session, scroll.split())
        self.assertNotIn(scroll, p.inventory)
        self.assertIn("Second Attack", p.learned_skills)
        scroll = self.read(session, "third attack")
        self.assertIn(scroll, p.inventory)
        self.assertNotIn("Third Attack", p.learned_skills)

    def test_duplicate_read_and_old_mastery_are_preserved(self):
        p, session, messages = self.player_and_session()
        p.learned_skills = ["Second Attack", "Third Attack"]
        p.skill_proficiencies = {"Second Attack": 82, "Third Attack": 41}
        scroll = self.read(session, "second attack")
        self.assertIn(scroll, p.inventory)
        self.assertIn("already know", messages[-1])
        leveling.sync_universal_skills(p)
        self.assertEqual(p.skill_proficiencies["Second Attack"], 82)
        self.assertEqual(p.skill_proficiencies["Third Attack"], 41)
        self.assertNotIn("Fourth Attack", p.learned_skills)

    def test_renamed_skill_backfill_preserves_progress_and_training(self):
        p, _, _ = self.player_and_session("taijutsu", level=20)
        p.learned_skills = ["Appraisal", "Examine"]
        p.skill_proficiencies = {"Appraisal": 65, "Examine": 20}
        p.practiced_skills = ["Appraisal"]
        p.signature_move = "Appraisal"
        leveling.sync_universal_skills(p)
        self.assertEqual(p.learned_skills.count("Examine"), 1)
        self.assertNotIn("Appraisal", p.learned_skills)
        self.assertEqual(p.skill_proficiencies["Examine"], 65)
        self.assertIn("Examine", p.practiced_skills)
        self.assertEqual(p.signature_move, "Examine")

    def test_level_up_does_not_award_numbered_attack(self):
        p, _, _ = self.player_and_session(level=49)
        p.village_rank = "jounin"
        p.experience = leveling.cumulative_xp_for_level(49)
        with patch.object(leveling.shinobi_notices, "announce_level"):
            leveling.grant_experience(p, leveling.xp_band_for_level(49))
        self.assertEqual(p.level, 50)
        self.assertNotIn("Third Attack", p.learned_skills)


if __name__ == "__main__":
    unittest.main()
