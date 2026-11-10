"""Complete help-catalog audit: commands, staff pages, current rules and upgrades.

Builds the same catalogs used by the live server, rather than checking only
a small manually maintained list. Existing staff-authored data/help is safe.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import commands
import help_audit
import help_system
from help_command_overrides import PAGES as REVIEWED, STAFF_GUIDE


class HelpCatalogAuditTests(unittest.TestCase):
    def setUp(self):
        self.pages = {e["primary_keyword"]: e for e in help_system.DEFAULT_HELP_ENTRIES}
        self.lookup = {alias.casefold() for e in self.pages.values()
                       for alias in [e["primary_keyword"], *e["keywords"]]}

    def test_all_registered_commands_resolve_to_help_pages(self):
        missing = set(commands.COMMANDS) - self.lookup
        self.assertEqual(missing, set())
        self.assertIn("immortal commands", self.lookup)

    def test_all_missing_documentation_now_has_real_syntax(self):
        for command, reviewed in REVIEWED.items():
            with self.subTest(command=command):
                self.assertIn(command, commands.COMMANDS)
                self.assertIn(command, self.pages)
                body = self.pages[command]["body"]
                self.assertNotIn("[arguments]", body)
                self.assertNotIn("Try the command without arguments", body)
                self.assertIn("Syntax:", body)
                self.assertIn("Description:", body)
                self.assertIn("Date:", body)
                self.assertIn(reviewed, body)

    def test_group_ban_and_crafting_keep_current_instructions(self):
        group = self.pages["group"]["body"].lower()
        self.assertIn("group all", group)
        self.assertIn("follow", group)
        self.assertNotIn("group invite", group)
        self.assertNotIn("group accept", group)
        self.assertNotIn("same ip", group)
        self.assertIn("ban country", self.pages["ban"]["body"].lower())
        self.assertIn("no wood", self.pages["craft"]["body"].lower())
        self.assertIn("rarity is never shown", self.pages["examine"]["body"].lower())

    def test_cross_class_xp_staff_and_chakra_paper_docs(self):
        self.assertIn("Narakumi", self.pages["classes"]["body"])
        self.assertIn("class", self.pages["read"]["body"].lower())
        self.assertIn("overflow", self.pages["experience"]["body"].lower())
        self.assertIn("more than one level", self.pages["experience"]["body"].lower())
        self.assertIn("level 10", self.pages["channel"]["body"].lower())
        self.assertIn("level 25", self.pages["channel"]["body"].lower())
        self.assertIn("hedit delete", self.pages["hedit"]["body"].lower())
        self.assertIn("MPEDIT", self.pages["immortal commands"]["body"])

    def test_staff_index_only_visible_to_authenticated_staff(self):
        self.assertTrue(STAFF_GUIDE["staff_only"])
        page = self.pages["immortal commands"]
        regular = SimpleNamespace(account=SimpleNamespace(staff_level="player"))
        helper = SimpleNamespace(account=SimpleNamespace(staff_level="helper"))
        self.assertFalse(help_system._may_view_page(regular, page))
        self.assertTrue(help_system._may_view_page(helper, page))
        self.assertTrue(help_system._may_view_page(regular, self.pages["help"]))

    def test_system_pages_refresh_but_staff_edits_survive(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(help_system, "HELP_DIR", temporary):
            help_system.seed_default_help()
            self.assertTrue((Path(temporary) / "immortal_commands.json").is_file())
            page = dict(help_system.find_by_keyword("classes"))
            page["body"] = "Old system-owned class description"
            help_system.save_entry(page)
            help_system.seed_default_help()
            self.assertIn("Narakumi", help_system.find_by_keyword("classes")["body"])

            page = dict(help_system.find_by_keyword("group"))
            page["body"] = "Staff-customized group instructions"
            page["updated_by"] = "Builder"
            help_system.save_entry(page)
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword("group")["body"],
                             "Staff-customized group instructions")

    def test_all_existing_packaged_json_help_is_well_formed(self):
        root = Path(__file__).resolve().parent / "helpfiles"
        entries = list(root.glob("*.json"))
        self.assertGreaterEqual(len(entries), 450)
        filenames = set()
        for path in entries:
            with self.subTest(file=path.name):
                self.assertNotIn(path.name.casefold(), filenames)
                filenames.add(path.name.casefold())
                page = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(page.get("primary_keyword"))
                self.assertIsInstance(page.get("keywords"), list)
                self.assertTrue(page.get("title"))
                self.assertTrue(page.get("body"))


if __name__ == "__main__":
    unittest.main()
