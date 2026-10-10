"""Each jutsu gets a distinct visible three-shade name in actual output."""

import re
import unittest

import data_jutsu
import help_system
import jutsu_colors
from session import Session
from unittest.mock import patch


class JutsuColorTests(unittest.TestCase):
    def test_every_jutsu_has_distinct_multicolor_palette(self):
        self.assertEqual(len(jutsu_colors.SCHEMES), len(data_jutsu.JUTSU))
        self.assertEqual(len(set(jutsu_colors.SCHEMES.values())), len(data_jutsu.JUTSU))
        for key in data_jutsu.JUTSU:
            colored = jutsu_colors.colorful_name(key)
            shades = set(re.findall(r"&\[(\d+)\]", colored))
            self.assertGreaterEqual(len(shades), 2, key)
        self.assertNotEqual(jutsu_colors.SCHEMES["karyuu endan"],
                            jutsu_colors.SCHEMES["water dragon jutsu"])

    def test_send_styles_names_without_changing_plain_text(self):
        output = []
        session = Session(output.append, lambda: None)
        line = "You use Karyuu Endan; Water Dragon Jutsu follows."
        session.send_jutsu(line)
        shades = re.findall(r"\x1b\[38;5;(\d+)m", output[-1])
        self.assertGreaterEqual(len(set(shades)), 4)
        self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", output[-1]), line + "\r\n")
        session.color_enabled = False
        session.send_jutsu(line)
        self.assertEqual(output[-1], line + "\r\n")
        session.color_enabled = True
        session.send_jutsu("&BWater Dragon Jutsu&x is ready.")
        self.assertIn("\x1b[38;5;", output[-1])
        self.assertIn("Water Dragon Jutsu is ready.", re.sub(r"\x1b\[[0-9;]*m", "", output[-1]))
        session.send("Water Dragon Jutsu is listed in skills.")
        self.assertNotIn("\x1b[38;5;", output[-1])

    def test_help_page_uses_palette(self):
        output = []
        session = Session(output.append, lambda: None)
        entry = {"primary_keyword": "karyuu endan", "keywords": ["karyuu endan"],
                 "title": "Karyuu Endan", "body": "Syntax: perform karyuu endan <target>"}
        with patch.object(help_system, "find_by_keyword", return_value=entry):
            help_system.cmd_help(session, ["karyuu", "endan"])
        self.assertGreaterEqual(output[-1].count("\x1b[38;5;"), 4)


if __name__ == "__main__":
    unittest.main()
