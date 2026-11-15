"""Regression tests for normal and bright ANSI foreground codes."""
import unittest
import colors

class ColorIntensityTests(unittest.TestCase):
    PAIRS = {
        "R": ("r", 31, 91), "G": ("g", 32, 92),
        "Y": ("y", 33, 93), "B": ("b", 34, 94),
        "C": ("c", 36, 96), "M": ("m", 35, 95),
        "W": ("w", 37, 97), "D": ("d", 90, 37),
    }

    def test_pairs_and_intensity_reset(self):
        for normal, (bright, low, high) in self.PAIRS.items():
            with self.subTest(normal=normal):
                self.assertEqual(colors.ANSI_CODES["&" + normal],
                                 f"\x1b[22;{low}m")
                self.assertEqual(colors.ANSI_CODES["&" + bright],
                                 f"\x1b[22;{high}m")
                self.assertNotEqual(colors.ANSI_CODES["&" + normal],
                                    colors.ANSI_CODES["&" + bright])

    def test_bright_to_normal_and_back(self):
        for normal, (bright, _, _) in self.PAIRS.items():
            with self.subTest(normal=normal):
                self.assertEqual(
                    colors.render(f"&{bright}Bright&{normal}Normal&{bright}Bright&x", True),
                    colors.ANSI_CODES["&" + bright] + "Bright" +
                    colors.ANSI_CODES["&" + normal] + "Normal" +
                    colors.ANSI_CODES["&" + bright] + "Bright" +
                    colors.ANSI_CODES["&x"])

    def test_color_off_and_literal_codes(self):
        self.assertEqual(colors.render("&&r &rBright &RNormal &gLight &GDark&x", False),
                         "&r Bright Normal Light Dark")
        self.assertEqual(colors.render("&&r &rBright", True),
                         "&r " + colors.ANSI_CODES["&r"] + "Bright")

    def test_numeric_codes_unchanged(self):
        self.assertEqual(colors.render("&[196]Red&208Orange&x", True),
                         "\x1b[38;5;196mRed\x1b[38;5;208mOrange\x1b[0m")

if __name__ == "__main__":
    unittest.main()
