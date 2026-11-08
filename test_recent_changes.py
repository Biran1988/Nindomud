"""Recent player-facing updates are published to the in-game Changes board."""
import unittest

import changelog
import commands


class RecentChangesTests(unittest.TestCase):
    def test_changes_lists_recent_features_in_order(self):
        entries = dict(changelog.CHANGELOG)
        expected = {
            "15.425": ("MISSION REQUEST", "MISSION INFO", "MISSION FAIL", "30-minute", "flagged Mission"),
            "15.426": ("Advanced Tracking", "level-20", "PERFORM TRACK", "area boundaries"),
            "15.427": ("Farming", "Medicinal Herbs", "35 Farming XP"),
            "15.428": ("Info Scroll", "WRITE INFO SCROLL", "EXAMINE INFO SCROLL", "multiline"),
            "15.429": ("LOOK <player>", "wielded swords", "off-hand", "inventory"),
        }
        for version, terms in expected.items():
            self.assertIn(version, entries)
            for term in terms:
                with self.subTest(version=version, term=term):
                    self.assertIn(term, entries[version])
        all_versions = [version for version, _ in changelog.CHANGELOG]
        positions = [all_versions.index(version) for version in expected]
        self.assertEqual(positions, sorted(positions))
        for version in ("15.432", "15.433", "15.434"):
            self.assertIn(version, entries)

    def test_changes_command_outputs_newest_entries(self):
        pages = []
        class Session:
            def send_paginated(self, output):
                pages.append(output)
        commands.cmd_changes(Session(), [])
        self.assertTrue(pages)
        for version in ("15.425", "15.426", "15.427", "15.428", "15.429"):
            self.assertIn(version, pages[0])
        self.assertLess(pages[0].index("15.429"), pages[0].index("15.425"))

    def test_road_migration_omitted_from_new_changelog_entries(self):
        text = "\n".join(summary for _, summary in changelog.CHANGELOG[-7:]).lower()
        # Player-facing roadside missions belong on the board. The
        # internal migration details that installed the road network do not.
        self.assertNotIn("road migration", text)
        self.assertNotIn("bandit camp", text)
        self.assertNotIn("road junction", text)


if __name__ == "__main__":
    unittest.main()
