"""Regression tests for anime-inspired jutsu in every primary class."""
import unittest
from unittest.mock import patch

import anime_arts
import combat
import commands
import data_jutsu
import help_system
import jutsu_shortcuts
import leveling
from models import Player


class AnimeInspiredJutsuTests(unittest.TestCase):
    def test_sixteen_real_registered_attacks_in_four_classes(self):
        entries = anime_arts.jutsu_entries()
        self.assertEqual(len(entries), 16)
        self.assertEqual(len({a["jutsu_id"] for a in entries.values()}), 16)
        for school in ("ninjutsu", "taijutsu", "genjutsu", "bukijutsu"):
            arts = {key: art for key, art in entries.items()
                    if art["class_requirement"] == school}
            self.assertEqual({art["level_requirement"] for art in arts.values()},
                             {25, 50, 75, 100})
            for key, original in arts.items():
                live = data_jutsu.JUTSU[key]
                self.assertEqual(live["display_name"], original["display_name"])
                self.assertGreater(live["damage"][0], 0)
                self.assertGreaterEqual(live["damage"][1], live["damage"][0])
                self.assertIn(live["effect"], __import__("status_effects").EFFECT_DEFS)
                self.assertEqual(live["jutsu_type"], "attack")
                self.assertTrue(data_jutsu.scroll_can_cross_class(live))
                self.assertIn(key, data_jutsu.JUTSU_SHORTCUTS)
                self.assertEqual(data_jutsu.match_prefix([data_jutsu.JUTSU_SHORTCUTS[key]]),
                                 (key, 1))

    def test_level_unlock_and_retroactive_grant_per_class(self):
        for school in ("ninjutsu", "taijutsu", "genjutsu", "bukijutsu"):
            with self.subTest(school=school):
                player = Player("AnimeTester", "AnimeTester", level=100,
                                primary_class=school)
                new = anime_arts.jutsu_entries()
                own = {x["display_name"] for x in new.values()
                       if x["class_requirement"] == school}
                others = {x["display_name"] for x in new.values()
                          if x["class_requirement"] != school}
                with patch("storage.save_player"):
                    leveling.sync_universal_skills(player)
                self.assertTrue(own.issubset(player.learned_skills))
                self.assertTrue(others.isdisjoint(player.learned_skills))
                for name in own:
                    self.assertIn(name, player.skill_proficiencies)

    def test_level_rules_and_weapon_requirement_are_real(self):
        s = Player("SwordTester", "SwordTester", level=100,
                   primary_class="bukijutsu")
        s.learned_skills.append("Starstream Sword Dance")
        art = data_jutsu.JUTSU["starstream sword dance"]
        self.assertFalse(combat._can_use_jutsu(s, art, "starstream sword dance"))
        s.equipment["wielded"] = "Iron Sword"
        self.assertTrue(combat._can_use_jutsu(s, art, "starstream sword dance"))
        s.equipment["wielded"] = "Kunai"
        self.assertFalse(combat._can_use_jutsu(s, art, "starstream sword dance"))
        n = Player("FireTester", "FireTester", level=100,
                   primary_class="ninjutsu")
        n.learned_skills.append("Dragonfire Pulse")
        fire = data_jutsu.JUTSU["dragonfire pulse"]
        n.chakra_nature = "water"
        self.assertFalse(combat._can_use_jutsu(n, fire, "dragonfire pulse"))
        n.chakra_nature = "fire"
        self.assertTrue(combat._can_use_jutsu(n, fire, "dragonfire pulse"))

    def test_help_and_shortcuts_are_synchronized(self):
        pages = {p["primary_keyword"]: p for p in help_system.DEFAULT_HELP_ENTRIES}
        for key, art in anime_arts.jutsu_entries().items():
            self.assertIn(key, pages)
            body = pages[key]["body"]
            self.assertIn(str(art["level_requirement"]), body)
            self.assertIn(data_jutsu.JUTSU[key]["effect"].replace("_", " "), body)
            self.assertIn(str(data_jutsu.JUTSU[key]["damage"][0]), body)
        self.assertIn("anime arts", pages)
        # Full command registry import runs the production collision checks.
        jutsu_shortcuts.validate_shortcuts(
            data_jutsu.JUTSU, data_jutsu.JUTSU_ALIASES,
            set(commands.COMMANDS))


if __name__ == '__main__':
    unittest.main()
