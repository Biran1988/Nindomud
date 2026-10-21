"""Regression tests for shorthand xterm-256 markup."""
import unittest
import colors


class NumericColorTests(unittest.TestCase):
    def test_numeric_shorthand(self):
        self.assertEqual(colors.render("&208Ember&x", True), "\x1b[38;5;208mEmber\x1b[0m")
        self.assertEqual(colors.render("&51Cyan", True), "\x1b[38;5;51mCyan")
        self.assertEqual(colors.render("&0Black", True), "\x1b[38;5;0mBlack")

    def test_bracketed_and_legacy_still_work(self):
        self.assertEqual(colors.render("&[223]Sand &RRed&x", True), "\x1b[38;5;223mSand \x1b[31mRed\x1b[0m")

    def test_color_off_and_literal_ampersand(self):
        self.assertEqual(colors.render("&208Ember &[223]Sand &RRed", False), "Ember Sand Red")
        self.assertEqual(colors.render("&&208 is literal, &&R too", True), "&208 is literal, &R too")

    def test_invalid_numeric_code(self):
        self.assertEqual(colors.render("&999Invalid", True), "Invalid")


if __name__ == "__main__":
    unittest.main()
