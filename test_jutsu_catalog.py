"""Character-class jutsu list and full immortal roster regression coverage."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

import clone_control
import commands
import data_jutsu
from models import Player


class JutsuCatalogTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("CatalogTester", "CatalogTester", level=20,
                             village="leaf", clan="nara", primary_class="taijutsu")
        self.player.learned_skills = ["Dynamic Entry"]
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          send=Mock(), send_paginated=Mock())

    def test_player_sees_all_class_techniques_even_when_locked(self):
        lines = commands.build_jutsu_catalog_lines(self.player)
        text = "\n".join(lines)
        self.assertIn("Dynamic Entry", text)
        self.assertIn("Tamashiwara", text)  # future Taijutsu unlock
        self.assertIn("General Jutsu", text)
        self.assertIn("Barrier", text)  # shared across classes
        self.assertNotIn("Shadow Clone Jutsu", text)
        self.assertNotIn("Narakumi", text)
        self.assertNotIn("Throw Kunai", text)
        self.assertNotIn("100 Years of Death", text)  # undiscovered scroll
        self.assertIn("&GLearned&x", text)
        self.assertIn("&DLocked&x", text)

    def test_immortal_sees_every_class_and_special_entries(self):
        lines = commands.build_jutsu_catalog_lines(self.player, immortal=True)
        text = "\n".join(lines)
        for name in ("Ninjutsu", "Taijutsu", "Genjutsu", "Bukijutsu"):
            self.assertIn(f"[ {name} ]", text)
        for name in ("Shadow Clone Jutsu", "Dynamic Entry", "Narakumi",
                     "Throw Kunai", "100 Years of Death"):
            self.assertIn(name, text)
        self.assertIn("[Scroll]", text)
        self.assertIn("[Release]", text)

    def test_staff_access_is_based_on_account_rank_not_player_class(self):
        commands.dispatch(self.session, "jutsu", ["all"])
        shown = self.session.send_paginated.call_args.args[0]
        self.assertIn("Dynamic Entry", shown)
        self.assertNotIn("Shadow Clone Jutsu", shown)
        self.session.send_paginated.reset_mock()
        self.session.account.staff_level = "helper"
        commands.dispatch(self.session, "jutsu", ["all"])
        shown = self.session.send_paginated.call_args.args[0]
        self.assertIn("Shadow Clone Jutsu", shown)
        self.assertIn("Throw Kunai", shown)

    def test_requires_all_keyword_and_is_registered(self):
        self.assertIs(commands.COMMANDS["jutsu"], commands.cmd_jutsu)
        commands.dispatch(self.session, "jutsu", [])
        self.assertIn("Usage: jutsu all", self.session.send.call_args.args[0])
        self.session.send_paginated.assert_not_called()

    def test_all_learned_scroll_only_appears_in_personal_catalog(self):
        self.player.learned_skills.append("100 Years of Death")
        text = "\n".join(commands.build_jutsu_catalog_lines(self.player))
        self.assertIn("100 Years of Death", text)

    def test_command_available_during_sleep_and_clone_recon(self):
        self.player.position = "sleeping"
        commands.dispatch_line(self.session, "jutsu all")
        self.session.send_paginated.assert_called_once()
        self.assertIn("jutsu", clone_control.SENSE_VERBS)

    def test_every_entry_from_class_registry_is_represented_for_immortals(self):
        lines = commands.build_jutsu_catalog_lines(self.player, immortal=True)
        text = "\n".join(lines)
        for jutsu in data_jutsu.JUTSU.values():
            if jutsu["class_requirement"] in {"taijutsu", "ninjutsu", "genjutsu", "bukijutsu", "general"}:
                self.assertIn(jutsu["display_name"], text)


if __name__ == "__main__":
    unittest.main()
