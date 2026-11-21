"""SMAUGFUSS classic foreground intensity regression coverage."""
import unittest
import colors


class ColorIntensityTests(unittest.TestCase):
    PAIRS = {
        "r": ("R", "31"), "g": ("G", "32"), "y": ("Y", "33"),
        "b": ("B", "34"), "c": ("C", "36"),
        "p": ("P", "35"), "m": ("M", "35"), "w": ("W", "37"),
    }

    def test_classic_dark_and_bright_ansi(self):
        for dark, (bright, code) in self.PAIRS.items():
            with self.subTest(code=dark):
                self.assertEqual(colors.ANSI_CODES["&" + dark], f"\x1b[0;{code}m")
                self.assertEqual(colors.ANSI_CODES["&" + bright], f"\x1b[1;{code}m")

    def test_switching_bright_to_dark(self):
        for dark, (bright, _) in self.PAIRS.items():
            expected = (colors.ANSI_CODES["&"+bright]+"Bright"
                        +colors.ANSI_CODES["&"+dark]+"Dark"
                        +colors.ANSI_CODES["&"+bright]+"Bright"
                        +colors.ANSI_CODES["&x"])
            self.assertEqual(colors.render(f"&{bright}Bright&{dark}Dark&{bright}Bright&x", True), expected)

    def test_gray_white_and_purple_pink(self):
        self.assertEqual(colors.render("&wGray&WWhite&pPurple&PPink&x", True),
                         "\x1b[0;37mGray\x1b[1;37mWhite\x1b[0;35mPurple\x1b[1;35mPink\x1b[0m")
        self.assertEqual(colors.ANSI_CODES["&m"], colors.ANSI_CODES["&p"])
        self.assertEqual(colors.ANSI_CODES["&M"], colors.ANSI_CODES["&P"])

    def test_literal_and_plain(self):
        self.assertEqual(colors.render("&&r &rDark &RBright &pPurple &PPink&x", False), "&r Dark Bright Purple Pink")
        self.assertEqual(colors.render("&&r &rDark", True), "&r " + colors.ANSI_CODES["&r"] + "Dark")

    def test_extended_256_codes_and_reset_unchanged(self):
        self.assertEqual(colors.render("&[196]Red&208Orange&x", True),
                         "\x1b[38;5;196mRed\x1b[38;5;208mOrange\x1b[0m")
        self.assertEqual(colors.ANSI_CODES["&x"], "\x1b[0m")


if __name__ == "__main__":
    unittest.main()
