"""WHO list color redesign regression tests (display-only; saves stay untouched)."""
import re
import unittest

import commands
import ooc_titles


def visible(text):
    return re.sub(r"&\\[\\d+\\]|&[A-Za-z]", "", text)


class WhoVisualIdentityTests(unittest.TestCase):
    def test_all_six_village_labels_and_palettes(self):
        expected = {
            "leaf": ("Konoha", (196, 124)),
            "water": ("Mist", (39, 33)),
            "cloud": ("Cloud", (250, 69)),
            "sand": ("Sand", (223, 180)),
            "stone": ("Earth", (94, 114)),
            "whirlpool": ("Uzushio", (39, 87)),
        }
        for village, (name, colors) in expected.items():
            with self.subTest(village=village):
                actual = commands._who_village_name(village)
                self.assertEqual(visible(actual), name.ljust(7))
                self.assertIn(f"&[{colors[0]}]{name[0]}", actual)
                self.assertIn(f"&[{colors[1]}]{name[1]}", actual)
        self.assertEqual(commands.WHO_VILLAGE_WIDTH, 7)

    def test_rank_colors_and_visible_width(self):
        expected = {
            "student": ("Student", (244, 250)),
            "genin": ("Genin", (34, 121)),
            "chunin": ("Chuunin", (30, 51)),
            "special jonin": ("Sp.Jounin", (99, 183)),
            "jonin": ("Jounin", (214, 220)),
        }
        for rank, (label, colors) in expected.items():
            with self.subTest(rank=rank):
                self.assertEqual(commands.RANK_WHO_LABEL[rank], label)
                self.assertEqual(commands.RANK_WHO_COLORS[rank], colors)
                text = commands._who_rank_name(label, colors)
                self.assertEqual(visible(text), label.ljust(10))
                self.assertIn(f"&[{colors[0]}]{label[0]}", text)
                self.assertIn(f"&[{colors[1]}]{label[1]}", text)
        self.assertEqual(visible(commands._who_rank_name("Kage", commands.KAGE_WHO_COLORS, centered=True)), "   Kage   ")

    def test_clans_gradient_restarts_for_each_name_and_preserves_padding(self):
        for clan in ("Uzumaki", "Hozuki", "Chikamatsu", "None"):
            with self.subTest(clan=clan):
                styled = commands._who_clan_name(clan)
                self.assertEqual(visible(styled), clan.ljust(commands.WHO_CLAN_WIDTH))
                self.assertTrue(styled.startswith(f"&[{commands.WHO_CLAN_GRADIENT[0]}]{clan[0]}"))
                self.assertIn(f"&[{commands.WHO_CLAN_GRADIENT[-1]}]{clan[-1]}", styled)

    def test_existing_blue_level_and_custom_titles_remain(self):
        self.assertEqual(commands.WHO_LEVEL_COLOR, "&C")
        self.assertEqual(commands.WHO_PLAYER_NAME_COLOR, "&[172]")
        self.assertEqual(commands.WHO_BRACKET_COLOR, "&[250]")
        self.assertEqual(ooc_titles.display_name("Biran", "Inventor", "gray"), "Biran &wInventor&x")


if __name__ == "__main__":
    unittest.main()
