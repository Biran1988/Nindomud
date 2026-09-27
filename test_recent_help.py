"""Recent techniques have discoverable, accurate, upgrade-safe help pages."""

import tempfile
import unittest
from unittest.mock import patch

import data_jutsu
import help_system
import recent_help


class RecentHelpTests(unittest.TestCase):
    def test_every_jutsu_has_a_lookup_name_and_recent_arts_have_own_pages(self):
        entries = help_system.DEFAULT_HELP_ENTRIES
        primary = {entry["primary_keyword"] for entry in entries}
        aliases = {keyword for entry in entries for keyword in entry["keywords"]}
        self.assertFalse(set(data_jutsu.JUTSU) - (primary | aliases))
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


if __name__ == "__main__":
    unittest.main()
