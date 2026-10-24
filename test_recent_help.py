"""Recent techniques have discoverable, accurate, upgrade-safe help pages."""

import tempfile
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import data_jutsu
import commands
import help_system
import recent_help
from scripts import build_release


class RecentHelpTests(unittest.TestCase):
    def test_jubaku_and_stance_shortcuts_find_individual_pages(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, "HELP_DIR", temp):
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword("jubaku")["primary_keyword"], "jubaku satsu")
            self.assertEqual(help_system.find_by_keyword("kihon")["primary_keyword"], "kihon dachi")
            self.assertEqual(help_system.find_by_keyword("neko ashi")["primary_keyword"], "neko ashi dachi")
            self.assertEqual(help_system.find_by_keyword("sanchin")["primary_keyword"], "sanchin dachi")
            self.assertEqual(help_system.find_by_keyword("stance")["primary_keyword"], "taijutsu stances")
            self.assertIsNone(help_system.find_by_keyword("shadow"))  # two jutsu match
            self.assertIsNone(help_system.find_by_keyword("jubaku nonsense"))

    def test_release_contains_real_helpfiles_without_saved_data(self):
        with tempfile.TemporaryDirectory() as temp:
            build_release.build(Path(temp))
            with zipfile.ZipFile(Path(temp) / "Nindo_mud.zip") as archive:
                names = set(archive.namelist())
                self.assertEqual(len([name for name in names if name.startswith("helpfiles/")]),
                                 len(help_system.DEFAULT_HELP_ENTRIES))
                self.assertIn("helpfiles/jubaku_satsu.json", names)
                self.assertIn("helpfiles/kihon_dachi.json", names)
                self.assertIn("helpfiles/neko_ashi_dachi.json", names)
                self.assertIn("helpfiles/sanchin_dachi.json", names)
                self.assertIn("helpfiles/sharingan_upkeep.json", names)
                self.assertIn("helpfiles/water_release_glue_technique.json", names)
                self.assertFalse(any(any(char in name for char in '<>:"|?*\\') for name in names))
                self.assertIsNone(archive.testzip())
                self.assertFalse(any(name.startswith("data/") for name in names))
                self.assertIn("60% chance", archive.read("helpfiles/jubaku_satsu.json").decode())

    def test_every_command_and_sage_family_has_help(self):
        entries = help_system.DEFAULT_HELP_ENTRIES
        lookup = {keyword.lower() for entry in entries
                  for keyword in [entry["primary_keyword"], *entry["keywords"]]}
        self.assertEqual(set(commands.COMMANDS) - lookup, set())
        for family in ("toad", "snake", "slug", "ninken", "monkey"):
            self.assertIn(f"{family} sage mode", lookup)
            self.assertIn(f"sage {family}", lookup)
        self.assertIn("sage training", lookup)
        self.assertIn("sharingan upkeep", lookup)

    def test_every_jutsu_has_a_lookup_name_and_recent_arts_have_own_pages(self):
        entries = help_system.DEFAULT_HELP_ENTRIES
        primary = {entry["primary_keyword"] for entry in entries}
        aliases = {keyword for entry in entries for keyword in entry["keywords"]}
        public_keys = {key for key, data in data_jutsu.JUTSU.items() if not data.get("secret")}
        self.assertFalse(public_keys - (primary | aliases))
        for key in recent_help.DESCRIPTIONS:
            self.assertIn(key, primary)
            page = next(entry for entry in entries if entry["primary_keyword"] == key)
            self.assertIn(f"Syntax: ", page["body"])
            self.assertIn("Description:", page["body"])
            self.assertIn(str(data_jutsu.JUTSU[key]["chakra_cost"]), page["body"])
        self.assertNotIn("A damaging combat jutsu", " ".join(e["body"] for e in entries))

    def test_exact_page_precedes_group_alias_and_staff_edit_survives(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, "HELP_DIR", temp):
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword("choku zuki")["primary_keyword"], "choku zuki")
            self.assertEqual(help_system.find_by_keyword("samurai sabre")["primary_keyword"], "samurai sabre")
            self.assertEqual(help_system.find_by_keyword("demonic illusion hell viewing technique")["primary_keyword"], "demonic illusion")
            page = help_system.find_by_keyword("flying swallow")
            self.assertIn("30% chance", page["body"])
            page["body"] = "Custom builder page"
            page["updated_by"] = "Builder"
            help_system.save_entry(page)

            stale = help_system.find_by_keyword("multi-kunai throw")
            stale["body"] = "Old system description"
            help_system.save_entry(stale)
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword("flying swallow")["body"], "Custom builder page")
            self.assertIn("Throws three", help_system.find_by_keyword("multi-kunai throw")["body"])

    def test_revised_sharingan_page_reaches_existing_system_help(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, "HELP_DIR", temp):
            help_system.seed_default_help()
            page = help_system.find_by_keyword("sharingan")
            page["body"] = "Syntax: sharingan\n\nDescription: old per-tick notices\n\nDate: 2026-09-01"
            help_system.save_entry(page)
            help_system.seed_default_help()
            self.assertIn("every six minutes", help_system.find_by_keyword("sharingan")["body"])
            page = help_system.find_by_keyword("sharingan")
            page["updated_by"] = "Builder"
            page["body"] = "Builder's custom Sharingan guide"
            help_system.save_entry(page)
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword("sharingan")["body"], "Builder's custom Sharingan guide")

    def test_old_colon_help_filename_preserves_staff_edit(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, "HELP_DIR", temp):
            page = next(entry.copy() for entry in help_system.DEFAULT_HELP_ENTRIES
                        if entry["primary_keyword"] == "water release: glue technique")
            page["updated_by"] = "Builder"
            page["body"] = "Builder's custom Glue Technique guide"
            old_path = Path(temp) / "water_release:_glue_technique.json"
            old_path.write_text(json.dumps(page), encoding="utf-8")
            help_system.seed_default_help()
            self.assertFalse(old_path.exists())
            self.assertEqual(help_system.find_by_keyword(page["primary_keyword"])["body"], page["body"])


if __name__ == "__main__":
    unittest.main()
