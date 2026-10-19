"""Source-only deployment ZIP regression tests for the normal Nindo_mud server.

The download must be a direct ZIP of the regular multi-file Python code,
not a zip-in-zip and not the optional generated single-file launcher.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts import build_release


class ReleaseArchiveTests(unittest.TestCase):
    def test_normal_zip_contains_current_source_but_not_saved_data_or_standalone(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            build_release.build(output)
            archive_path = output / "Nindo_mud.zip"
            self.assertTrue(archive_path.is_file())
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
                self.assertNotIn("Nindo_mud", names)
                self.assertNotIn("Nindo_mud.zip", names)
                self.assertNotIn("UPDATE_INSTRUCTIONS.txt", names)
                for name in (
                    "main.py", "commands.py", "legendary_items.py",
                    "ui_palette.py", "test_kage_item_colors.py",
                    "changelog.py", "scripts/build_release.py",
                ):
                    self.assertIn(name, names)
                self.assertIn(b"def cmd_colorscheme", archive.read("commands.py"))
                self.assertIn(b"LEGENDARY_COLOR_SCHEMES", archive.read("legendary_items.py"))
                self.assertIn(b"15.328", archive.read("changelog.py"))
                self.assertFalse(any(
                    name == "data" or name.startswith("data/")
                    or name in {"world_state.json", "templates.json"}
                    for name in names
                ))
                # Test the actual multi-file source *inside the download*.
                install = output / "install"
                archive.extractall(install)
            preflight = subprocess.run(
                [sys.executable, str(install / "main.py"), "--preflight"],
                cwd=install, capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr[-3500:])


if __name__ == "__main__":
    unittest.main()
