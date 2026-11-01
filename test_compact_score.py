"""Score sheet should stay compact, complete and readable across MUD clients."""
import re
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

import changelog
import commands
import config
from models import Player


def plaintext(lines):
    return re.sub(r"&(?:\[\d+\]|.)", "", "\n".join(lines))


class CompactScoreTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Tester", "Tester", level=50,
                             village="leaf", clan="uchiha",
                             primary_class="bukijutsu", village_rank="chunin")

    def test_default_is_compact_without_losing_old_score_categories(self):
        lines = commands.build_score_lines(self.player, "Nobody")
        score = plaintext(lines)
        self.assertLessEqual(len(lines), 30)
        self.assertNotIn("\n\n", score)
        for text in (
            f"{config.MUD_NAME.upper()} CHARACTER SCORE", "SHINOBI PROFILE",
            "COMBAT INFORMATION", "ATTRIBUTES", "MISSION INFO",
            "Name:", "Village:", "Rank:", "Clan:", "Level:",
            "Experience:", "Next Level:", "Rank Level Cap:",
            "Advancement:", "Ryo:", "Age:", "Play Time:",
            "Sex:", "Skin Tone:", "Hair Color:", "Eye Color:",
            "Build:", "Personality:", "Health:", "Chakra:",
            "Stamina:", "Armor Class:", "Hit Roll:", "Damage Roll:",
            "Dodge Chance:", "Critical Chance:", "Initiative:",
            "Position:", "Fighting:", "Player Kills:", "Player Deaths:",
            "Strength:", "Wisdom:", "Constitution:", "Intelligence:",
            "Dexterity:", "Luck:", "Perception:", "Willpower:",
            "Chakra Control:", "Practice Points:", "Training Points:",
            "Active effects:", "Active missions:", "Missions completed:",
            "Reputation with",
        ):
            self.assertIn(text, score)
        self.assertNotIn("Equipped:", score)
        self.assertTrue(all(len(line) <= 78 for line in score.splitlines()))

    def test_resource_bars_show_actual_values_and_handle_zero_maximum(self):
        self.player.health = 50
        self.player.maximum_health = 100
        self.player.chakra = 0
        self.player.maximum_chakra = 0
        self.player.stamina = 125
        self.player.maximum_stamina = 100
        score = plaintext(commands.build_score_lines(self.player, "Nobody"))
        self.assertIn("Health: 50/100 [##...", score)
        self.assertIn("Chakra: 0/0 [.....]", score)
        self.assertIn("Stamina: 125/100 [#####]", score)

    def test_long_names_are_never_cut_or_misalign_other_columns(self):
        name = "Legendary Ninja With A Very Long Custom Name"
        rows = commands._score_fields(("Fighting", name), ("Rank", "Chunin"))
        shown = plaintext(rows)
        self.assertIn(name, shown)
        self.assertIn("Rank: Chunin", shown)
        self.assertEqual(len(rows), 2)

    def test_hidden_natures_remain_hidden_until_revealed(self):
        self.player.chakra_nature = "fire"
        self.player.chakra_nature_secondary = "earth"
        self.player.chakra_nature_tertiary = "water"
        score = plaintext(commands.build_score_lines(self.player, "Nobody"))
        self.assertNotIn("Chakra Nature:", score)
        self.player.chakra_nature_revealed = True
        self.player.chakra_nature_secondary_revealed = True
        self.player.chakra_nature_tertiary_revealed = True
        score = plaintext(commands.build_score_lines(self.player, "Nobody"))
        self.assertIn("Chakra Nature: Fire", score)
        self.assertIn("Secondary Nature: Earth", score)
        self.assertIn("Third Nature: Water", score)

    def test_score_command_staff_marker_and_changelog_entry(self):
        session = NS(player=self.player, combat_target=None,
                     account=NS(staff_level="implementor"), send=Mock())
        commands.cmd_score(session, [])
        score = plaintext(session.send.call_args.args[0].splitlines())
        self.assertIn("[Implementor]", score)
        self.assertIn("SHINOBI PROFILE", score)
        self.assertIn("15.389", dict(changelog.CHANGELOG))


if __name__ == "__main__":
    unittest.main()
