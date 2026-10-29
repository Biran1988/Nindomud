"""Regression coverage for the compact level command and score XP parity."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

import commands
import leveling
from models import Player


class LevelCommandTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("LevelTester", "LevelTester", level=25,
                             village="leaf", clan="nara", primary_class="taijutsu",
                             village_rank="chunin")
        self.player.experience = 15_500_000
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          combat_target=None, send=Mock())

    def test_level_matches_score_values_and_reports_remaining_xp(self):
        commands.dispatch(self.session, "level", [])
        shown = self.session.send.call_args.args[0]
        threshold = leveling.xp_for_next_level(self.player.level)
        self.assertEqual(threshold, 15_625_000)
        self.assertEqual(shown, "\n".join((
            commands._row("Level", 25, "Experience", 15_500_000),
            commands._row("Next Level", threshold, "XP Needed", 125_000),
            commands._row("Ninja Rank", "Chunin", "Rank Cap", 80),
        )))
        score = commands.build_score_lines(self.player, "Nobody")
        self.assertIn(commands._row("Level", 25, "Class", self.player.primary_class.capitalize()), score)
        self.assertIn(commands._row("Experience", 15_500_000, "Next Level", threshold), score)

    def test_maximum_level_needs_no_further_xp(self):
        self.player.level = leveling.MAX_LEVEL
        self.player.experience = leveling.xp_for_next_level(self.player.level)
        commands.cmd_level(self.session, [])
        shown = self.session.send.call_args.args[0]
        self.assertIn(commands._row("Next Level", self.player.experience, "XP Needed", 0), shown)

    def test_level_is_readable_while_sleeping_and_frozen(self):
        self.player.position = "sleeping"
        commands.dispatch_line(self.session, "level")
        self.assertIn("XP Needed", self.session.send.call_args.args[0])
        self.session.send.reset_mock()
        self.player.position = "standing"
        self.player.tsukuyomi_frozen = True
        commands.dispatch_line(self.session, "level")
        self.assertIn("XP Needed", self.session.send.call_args.args[0])

    def test_command_and_help_are_registered(self):
        self.assertIs(commands.COMMANDS["level"], commands.cmd_level)


if __name__ == "__main__":
    unittest.main()
