"""Automatic universal extra attacks, retired legacy scrolls and preserved mastery."""
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

    def test_every_class_receives_second_at_25_and_third_at_75_on_login(self):
        for ninja_class in ("bukijutsu", "ninjutsu", "taijutsu", "genjutsu"):
            for level, expected in (
                    (24, set()), (25, {"Second Attack"}),
                    (74, {"Second Attack"}),
                    (75, {"Second Attack", "Third Attack"}),
                    (250, {"Second Attack", "Third Attack"})):
                with self.subTest(ninja_class=ninja_class, level=level):
                    p, _, _ = self.player_and_session(ninja_class, level)
                    leveling.sync_universal_skills(p)
                    attacks = set(p.learned_skills) & {
                        "Second Attack", "Third Attack", "Fourth Attack", "Fifth Attack"}
                    self.assertEqual(attacks, expected)
                    if level >= 20:
                        self.assertIn("Handsigns", p.learned_skills)

    def test_legacy_scrolls_keep_vnums_but_do_not_teach_or_consume(self):
        expected = {"second attack": (31740, 25, "general"),
                    "third attack": (31741, 75, "general"),
                    "fourth attack": (31742, 75, "bukijutsu"),
                    "fifth attack": (31743, 90, "bukijutsu")}
        for name, (vnum, level, klass) in expected.items():
            self.assertEqual(catalog.vnum_for(name), vnum)
            self.assertEqual(data_jutsu.MULTI_ATTACK_SCROLLS[name]["level_requirement"], level)
            self.assertEqual(data_jutsu.MULTI_ATTACK_SCROLLS[name]["class_requirement"], klass)
            self.assertEqual(olc.OBJECT_TEMPLATES[vnum]["scroll_jutsu"], name)
        p, session, messages = self.player_and_session("genjutsu", 1)
        for key in ("second attack", "third attack"):
            scroll = self.read(session, key)
            self.assertIn(scroll, p.inventory)
            self.assertNotIn(key.title(), p.learned_skills)
            self.assertIn("automatically", messages[-1])
        self.assertEqual(p.skill_proficiencies.get("Second Attack"), None)

    def test_fourth_and_fifth_are_still_bukijutsu_scroll_only(self):
        p, session, messages = self.player_and_session()
        leveling.sync_universal_skills(p)
        for key in ("fourth attack", "fifth attack"):
            self.assertNotIn(key.title(), p.learned_skills)
            scroll = self.read(session, key)
            self.assertNotIn(scroll, p.inventory)
            self.assertIn(key.title(), p.learned_skills)
            self.assertEqual(p.skill_proficiencies[key.title()], 0)
            self.assertIn("learned", messages[-1])
        outsider, outsider_session, _ = self.player_and_session("taijutsu")
        scroll = self.read(outsider_session, "fourth attack")
        self.assertIn(scroll, outsider.inventory)
        self.assertNotIn("Fourth Attack", outsider.learned_skills)

    def test_below_level_restricted_scrolls_are_not_consumed(self):
        for key, level in (("fourth attack", 74), ("fifth attack", 89)):
            p, session, _ = self.player_and_session(level=level)
            scroll = self.read(session, key)
            self.assertIn(scroll, p.inventory)
            self.assertNotIn(key.title(), p.learned_skills)

    def test_old_mastery_is_preserved_when_login_backfills_skills(self):
        p, session, messages = self.player_and_session()
        p.learned_skills = ["Second Attack", "Fourth Attack"]
        p.skill_proficiencies = {"Second Attack": 82,
                                 "Third Attack": 41, "Fourth Attack": 33}
        leveling.sync_universal_skills(p)
        self.assertEqual(p.learned_skills.count("Second Attack"), 1)
        self.assertEqual(p.learned_skills.count("Third Attack"), 1)
        self.assertEqual(p.skill_proficiencies["Second Attack"], 82)
        self.assertEqual(p.skill_proficiencies["Third Attack"], 41)
        self.assertEqual(p.skill_proficiencies["Fourth Attack"], 33)
        self.assertNotIn("Fifth Attack", p.learned_skills)
        old_scroll = self.read(session, "second attack")
        self.assertIn(old_scroll, p.inventory)
        self.assertIn("no longer required", messages[-1])
        duplicate = self.read(session, "fourth attack")
        self.assertIn(duplicate, p.inventory)
        self.assertIn("already know", messages[-1])

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

    def test_level_up_unlocks_at_25_and_75_without_scrolls(self):
        for ninja_class in ("bukijutsu", "ninjutsu", "taijutsu", "genjutsu"):
            for before, skill in ((24, "Second Attack"), (74, "Third Attack")):
                with self.subTest(ninja_class=ninja_class, level=before):
                    p, _, _ = self.player_and_session(ninja_class, before)
                    p.village_rank = "jounin"
                    p.experience = leveling.cumulative_xp_for_level(before)
                    with patch.object(leveling.shinobi_notices, "announce_level"):
                        leveling.grant_experience(p, leveling.xp_band_for_level(before))
                    self.assertEqual(p.level, before + 1)
                    self.assertIn(skill, p.learned_skills)
                    self.assertEqual(p.skill_proficiencies[skill], 0)

    def test_combat_checks_new_level_gates_and_cascading_attacks(self):
        p, _, _ = self.player_and_session("genjutsu", level=24)
        p.learned_skills = ["Second Attack", "Third Attack"]
        p.skill_proficiencies = {"Second Attack": 100, "Third Attack": 100}
        self.assertEqual(combat._roll_extra_attacks(p), 0)
        p.level = 25
        self.assertEqual(combat._roll_extra_attacks(p), 1)
        p.level = 74
        self.assertEqual(combat._roll_extra_attacks(p), 1)
        p.level = 75
        self.assertEqual(combat._roll_extra_attacks(p), 2)


if __name__ == "__main__":
    unittest.main()
