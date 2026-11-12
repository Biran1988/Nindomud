"""Release checks for advanced worker and elemental mastery player documentation."""
import tempfile
import unittest
from unittest.mock import patch

import changelog
import help_system


class CloneElementHelpRolloutTests(unittest.TestCase):
    def test_system_help_topics_seed_and_display(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, 'HELP_DIR', temp):
            help_system.seed_default_help()
            cases = {
                'advanced shadow clone jutsu': ('PERFORM ADVANCED SHADOW CLONE JUTSU MINE', 'TRAIN', '500 Chakra', 'apartment'),
                'workclone': ('PERFORM ADVANCED SHADOW CLONE JUTSU STATUS', 'PERFORM ADVANCED SHADOW CLONE JUTSU RETURN', 'with steel axe'),
                'elemental mastery': ('ELEMENTS', '100%', '+15%', 'Chakra Paper'),
            }
            for topic, phrases in cases.items():
                page = help_system.find_by_keyword(topic)
                self.assertIsNotNone(page, topic)
                for phrase in phrases:
                    self.assertIn(phrase, page['body'])
                self.assertIn('\n\n', page['body'])
                self.assertNotIn('\\n', page['body'])

    def test_staff_help_is_preserved_on_restart(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, 'HELP_DIR', temp):
            help_system.seed_default_help()
            custom = help_system.find_by_keyword('workclone')
            custom['body'] = 'Staff-customized help text'
            custom['updated_by'] = 'Builder'
            help_system.save_entry(custom)
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword('workclone')['body'], custom['body'])

    def test_changes_has_gameplay_and_documentation_versions(self):
        versions = dict(changelog.CHANGELOG)
        self.assertIn('Shadow Clone', versions['15.449'])
        self.assertIn('Elemental Mastery', versions['15.450'])
        self.assertIn('HELP WORKCLONE', versions['15.451'])
        ordered_versions = [version for version, _ in changelog.CHANGELOG]
        expected = [f'15.{revision}' for revision in range(449, 463)]
        start = ordered_versions.index(expected[0])
        self.assertEqual(ordered_versions[start:start + len(expected)], expected)


if __name__ == '__main__':
    unittest.main()
