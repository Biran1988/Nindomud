"""SWR/FUSS lowercase dark, uppercase bright ANSI regression tests."""
import unittest
import colors

class ColorIntensityTests(unittest.TestCase):
    PAIRS = {
        "r": ("R", "31", "91"), "g": ("G", "32", "92"),
        "y": ("Y", "33", "93"), "b": ("B", "34", "94"),
        "c": ("C", "36", "96"), "m": ("M", "35", "95"),
        "w": ("W", "37", "97"), "d": ("D", "90", "37"),
        "z": ("Z", "30", "90"), "o": ("O", "38;5;130", "38;5;208"),
    }

    def test_pairs_and_intensity_reset(self):
        for dark, (bright, low, high) in self.PAIRS.items():
            with self.subTest(dark=dark):
                self.assertEqual(colors.ANSI_CODES["&" + dark], f"\x1b[22;{low}m")
                self.assertEqual(colors.ANSI_CODES["&" + bright], f"\x1b[22;{high}m")

    def test_bright_to_dark_and_back(self):
        for dark, (bright, _, _) in self.PAIRS.items():
            with self.subTest(dark=dark):
                self.assertEqual(
                    colors.render(f"&{bright}Bright&{dark}Dark&{bright}Bright&x", True),
                    colors.ANSI_CODES["&" + bright] + "Bright" +
                    colors.ANSI_CODES["&" + dark] + "Dark" +
                    colors.ANSI_CODES["&" + bright] + "Bright" +
                    colors.ANSI_CODES["&x"])

    def test_gray_white_and_purple_magenta(self):
        self.assertEqual(colors.render("&wGray&WWhite&mPurple&MMagenta&x", True),
                         "\x1b[22;37mGray\x1b[22;97mWhite\x1b[22;35mPurple\x1b[22;95mMagenta\x1b[0m")

    def test_color_off_and_literal_codes(self):
        self.assertEqual(colors.render("&&r &rDark &RBright &gDark &GBright&x", False),
                         "&r Dark Bright Dark Bright")
        self.assertEqual(colors.render("&&r &rDark", True),
                         "&r " + colors.ANSI_CODES["&r"] + "Dark")

    def test_numeric_codes_unchanged(self):
        self.assertEqual(colors.render("&[196]Red&208Orange&x", True),
                         "\x1b[38;5;196mRed\x1b[38;5;208mOrange\x1b[0m")

if __name__ == "__main__":
    unittest.main()
