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
        self.assertNotIn("1000 Years of Death", text)  # undiscovered scroll
        self.assertIn("&GLearned&x", text)
        self.assertIn("&DLocked&x", text)

    def test_immortal_sees_every_class_and_special_entries(self):
        lines = commands.build_jutsu_catalog_lines(self.player, immortal=True)
        text = "\n".join(lines)
        for name in ("Ninjutsu", "Taijutsu", "Genjutsu", "Bukijutsu"):
            self.assertIn(f"[ {name} ]", text)
        for name in ("Shadow Clone Jutsu", "Dynamic Entry", "Narakumi",
                     "Throw Kunai", "1000 Years of Death"):
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
        self.player.learned_skills.append("1000 Years of Death")
        text = "\n".join(commands.build_jutsu_catalog_lines(self.player))
        self.assertIn("1000 Years of Death", text)

    def test_command_available_during_sleep_and_clone_recon(self):
        self.player.position = "sleeping"
        commands.dispatch_line(self.session, "jutsu all")
        self.session.send_paginated.assert_called_once()
        self.assertIn("jutsu", clone_control.SENSE_VERBS)

    def catalog(self):
        return "\n".join(commands.build_jutsu_catalog_lines(self.player))

    def test_elements_appear_only_as_each_nature_is_revealed(self):
        self.player.primary_class = "ninjutsu"
        self.player.chakra_nature = "fire"
        self.player.chakra_nature_secondary = "water"
        self.player.learned_skills += ["Fireball Jutsu", "Hidden Mist Jutsu"]
        self.assertNotIn("Fireball Jutsu", self.catalog())
        self.assertNotIn("Hidden Mist Jutsu", self.catalog())
        self.player.chakra_nature_revealed = True
        self.assertIn("Fireball Jutsu", self.catalog())
        self.assertNotIn("Hidden Mist Jutsu", self.catalog())
        self.player.chakra_nature_secondary_revealed = True
        self.assertIn("Hidden Mist Jutsu", self.catalog())
        self.assertNotIn("Lightning Strike Jutsu", self.catalog())

    def test_release_unlock_adds_future_moves_even_outside_primary_class(self):
        self.player.primary_class = "genjutsu"
        self.player.level = 25
        self.player.chakra_nature = "water"
        self.player.chakra_nature_revealed = True
        self.player.chakra_nature_secondary = "earth"
        self.player.elemental_release_id = "wood_release"
        self.assertNotIn("Wood Splinter Barrage", self.catalog())
        self.player.chakra_nature_secondary_revealed = True
        self.assertIn("Wood Splinter Barrage", self.catalog())
        self.assertIn("Deep Forest Bloom", self.catalog())
        self.assertNotIn("Laser Current", self.catalog())
        self.assertNotIn("Chidori", self.catalog())

    def test_unearned_or_undiscovered_eye_jutsu_never_leak_from_old_learned_lists(self):
        self.player.primary_class = "ninjutsu"
        self.player.learned_skills += ["Kamui: Pocket Dimension", "Kamui: Intangibility", "Amaterasu"]
        self.assertNotIn("Kamui", self.catalog())
        self.assertNotIn("Amaterasu", self.catalog())
        self.player.bloodline_id = "sharingan"
        self.player.bloodline_mangekyo = True
        self.player.mangekyo_eye_1 = "amaterasu"
        self.player.mangekyo_eye_2 = "tsukuyomi"
        self.assertNotIn("Amaterasu", self.catalog())
        self.player.mangekyo_eyes_used = ["amaterasu"]
        self.assertIn("Amaterasu", self.catalog())
        self.assertNotIn("Tsukuyomi", self.catalog())
        self.assertNotIn("Kamui", self.catalog())
        commands.cmd_jutsu(self.session, ["shorts"])
        self.assertNotIn("Kamui", self.session.send_paginated.call_args.args[0])
        commands.cmd_skills(self.session, [])
        self.assertNotIn("Kamui", self.session.send.call_args.args[0])

    def test_skills_all_is_the_same_personal_catalog_and_can_be_read_while_sleeping(self):
        self.player.position = "sleeping"
        commands.dispatch_line(self.session, "skills all")
        self.assertEqual(self.session.send_paginated.call_args.args[0], self.catalog())
        self.assertIn("skills", clone_control.SENSE_VERBS)

    def test_special_powers_require_actual_acquisition(self):
        self.player.primary_class = "ninjutsu"
        self.player.level = 100
        self.player.learned_skills += ["Tailed Beast Bomb", "Six Paths Rinnegan"]
        self.assertNotIn("Tailed Beast Bomb", self.catalog())
        self.assertNotIn("Six Paths Rinnegan", self.catalog())
        self.player.jinchuriki_beast_key = "matatabi"
        self.assertIn("Tailed Beast Bomb", self.catalog())
        self.player.reincarnation = "indra"
        self.assertIn("Six Paths Rinnegan", self.catalog())
        self.assertNotIn("Six Paths Sage Mode", self.catalog())

    def test_every_entry_from_class_registry_is_represented_for_immortals(self):
        lines = commands.build_jutsu_catalog_lines(self.player, immortal=True)
        text = "\n".join(lines)
        for jutsu in data_jutsu.JUTSU.values():
            if jutsu["class_requirement"] in {"taijutsu", "ninjutsu", "genjutsu", "bukijutsu", "general"}:
                self.assertIn(jutsu["display_name"], text)


if __name__ == "__main__":
    unittest.main()
