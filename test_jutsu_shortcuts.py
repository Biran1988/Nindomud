"""Shortcut routing, command precedence, secrecy and normal casting rules."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import help_system
import jutsu_shortcuts
import world
from models import Player


class JutsuShortcutTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("PhoneTester", "PhoneTester", level=50,
                             village="leaf", clan="nara", primary_class="ninjutsu")
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          send=Mock(), send_paginated=Mock(), pending_cast=None,
                          combat_target=None, pvp_target=None)

    def test_complete_unique_and_no_command_abbreviation_collisions(self):
        mapping = data_jutsu.JUTSU_SHORTCUTS
        self.assertEqual(set(mapping), set(data_jutsu.JUTSU))
        self.assertEqual(len(set(mapping.values())), len(mapping))
        words = set(commands.COMMANDS) | set(world.DIRECTION_ALIASES) | set(world.OPPOSITE_DIRECTION)
        reserved = {word[:n] for word in words for n in range(1, len(word) + 1)}
        self.assertFalse(set(mapping.values()) & reserved)
        for key, short in mapping.items():
            self.assertTrue(short.isalnum() and short.isascii())
            self.assertEqual(data_jutsu.JUTSU_ALIASES.get(short, key), key)
        with self.assertRaises(ValueError):
            jutsu_shortcuts.validate_shortcuts(data_jutsu.JUTSU, data_jutsu.JUTSU_ALIASES, {"ras"})

    def test_all_shortcuts_and_full_names_preserve_target_boundaries(self):
        for key, short in data_jutsu.JUTSU_SHORTCUTS.items():
            with self.subTest(key=key):
                self.assertEqual(data_jutsu.match_prefix([short, "Rival".lower()]), (key, 1))
                self.assertEqual(data_jutsu.match_prefix(key.split() + ["bandit"]), (key, len(key.split())))
                with patch.object(commands, "cmd_use_jutsu") as cast:
                    commands.dispatch_line(self.session, short.upper() + " Rival")
                    cast.assert_called_once_with(self.session, key, ["Rival"])
                with patch.object(commands, "cmd_use_jutsu") as cast:
                    commands.dispatch_line(self.session, "per " + short + " Rival")
                    cast.assert_called_once_with(self.session, key, ["Rival"])

    def test_shortcut_tokens_are_exact_and_do_not_swallow_arguments(self):
        for short, key in (("bc", "blast cascade"), ("bcs", "blast clay shot"),
                           ("hmist", "hidden mist jutsu"), ("smove", "silent movement")):
            with patch.object(commands, "cmd_use_jutsu") as cast:
                commands.dispatch_line(self.session, short + " off")
                cast.assert_called_once_with(self.session, key, ["off"])
        with patch.object(commands, "cmd_use_jutsu") as cast:
            commands.dispatch_line(self.session, "ras")
            cast.assert_called_once_with(self.session, "rasengan", [])

    def test_every_registered_command_outranks_jutsu_prefixes(self):
        for name in commands.COMMANDS:
            with self.subTest(command=name), patch.dict(commands.COMMANDS, {name: Mock()}):
                commands.dispatch_line(self.session, name + " argument")
                commands.COMMANDS[name].assert_called_once_with(self.session, ["argument"])

    def test_movement_stays_movement_and_legacy_aliases_are_preserved(self):
        for word in set(world.DIRECTION_ALIASES) | set(world.OPPOSITE_DIRECTION):
            with patch.object(commands, "cmd_move") as move, patch.object(commands, "cmd_use_jutsu") as cast:
                commands.dispatch_line(self.session, word)
                move.assert_called_once_with(self.session, world.normalize_direction(word))
                cast.assert_not_called()
        for short, key in data_jutsu.JUTSU_ALIASES.items():
            self.assertEqual(data_jutsu.match_prefix(short.split() + ["bandit"]),
                             (key, len(short.split())))
        self.assertEqual(data_jutsu.match_prefix(["kamui"]), ("kamui pocket dimension", 1))
        self.assertEqual(data_jutsu.match_prefix(["shadow"]), (None, 0))
        self.assertEqual(data_jutsu.match_prefix(["e"]), (None, 0))

    def test_shortcuts_do_not_bypass_sleep_freeze_or_rampage(self):
        for state in ("sleeping", "tsukuyomi_frozen", "asleep", "frozen_until", "rampage_until", "downed_by"):
            with self.subTest(state=state), patch.object(commands, "cmd_use_jutsu") as cast:
                if state == "sleeping":
                    self.player.position = "sleeping"
                elif state == "asleep":
                    self.player.active_status_effects["asleep"] = {"duration": 10}
                else:
                    setattr(self.player, state, "Enemy" if state == "downed_by" else 10**12)
                commands.dispatch_line(self.session, "ras bandit")
                cast.assert_not_called()
                self.player.position = "standing"
                self.player.active_status_effects.clear()
                if state not in {"sleeping", "asleep"}:
                    setattr(self.player, state, None if state == "downed_by" else 0)

    def test_actual_cast_still_requires_practice_and_pays_normal_cost_cooldown(self):
        self.player.learned_skills = ["Camouflage"]
        self.player.skill_proficiencies = {"Camouflage": 50}
        self.player.practice_gate_enabled = True
        self.player.chakra = self.player.stamina = 500
        commands.dispatch_line(self.session, "cam on")
        self.assertIn("practice", self.session.send.call_args.args[0])
        self.assertEqual(self.player.chakra, 500)
        self.player.practiced_skills.append("Camouflage")
        with patch.object(combat, "grow_skill_from_usage"):
            commands.dispatch_line(self.session, "cam on")
        self.assertEqual((self.player.chakra, self.player.stamina), (485, 495))
        self.assertIn("camouflage", self.player.active_status_effects)
        commands.dispatch_line(self.session, "cam off")
        self.assertNotIn("camouflage", self.player.active_status_effects)
        commands.dispatch_line(self.session, "cam on")
        self.assertIn("recovering", self.session.send.call_args.args[0])
        self.assertEqual((self.player.chakra, self.player.stamina), (485, 495))

    def test_learned_list_and_catalog_keep_unknown_scroll_shortcuts_hidden(self):
        self.player.learned_skills = ["Dynamic Entry", "Shadow Shuriken Technique"]
        commands.cmd_jutsu(self.session, ["shorts"])
        text = self.session.send_paginated.call_args.args[0]
        self.assertIn("dyn", text)
        self.assertIn("ssh", text)
        self.assertNotIn("rseal", text)
        self.assertNotIn("rfree", text)
        catalog = "\n".join(commands.build_jutsu_catalog_lines(self.player))
        self.assertIn("Short: ssh", catalog)
        self.assertNotIn("rseal", catalog)
        self.player.clan = "uzumaki"
        self.player.village = "whirlpool"
        self.player.learned_skills.append("Reaper Death Seal")
        commands.cmd_jutsu(self.session, ["shortcuts"])
        self.assertIn("rseal", self.session.send_paginated.call_args.args[0])

    def test_all_public_shortcuts_find_normal_help_and_show_the_shortcut(self):
        with patch.object(help_system, "all_entries", return_value=help_system.DEFAULT_HELP_ENTRIES):
            for key, short in data_jutsu.JUTSU_SHORTCUTS.items():
                if not data_jutsu.JUTSU[key].get("secret"):
                    self.assertIsNotNone(help_system.find_by_keyword(short), key)
            help_system.cmd_help(self.session, ["hell"])
            self.assertIn("One-word shortcut:", self.session.send.call_args.args[0])
            self.assertIn("hell", self.session.send.call_args.args[0])

    def test_mastery_alias_shows_beast_percentage_without_toggling(self):
        self.player.jinchuriki_beast_key = "matatabi"
        self.player.jinchuriki_mastery = 42
        commands.dispatch_line(self.session, "mastery")
        self.assertIn("42%", self.session.send.call_args.args[0])
        self.assertFalse(self.player.tailed_beast_mode_active)
        self.player.position = "sleeping"
        commands.dispatch_line(self.session, "mastery")
        self.assertIn("42%", self.session.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
