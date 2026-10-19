"""Regression coverage: shipping release ZIP must contain the runnable server.

This prevents the regression where a ZIP had only source .py files, while
the user's service was launched from the stale standalone Nindo_mud executable.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts import build_release


class ReleaseArchiveTests(unittest.TestCase):
    def test_zip_includes_current_runnable_server_and_source_without_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)
            build_release.build(destination)
            archive_path = destination / "Nindo_mud.zip"
            standalone_path = destination / "Nindo_mud"
            self.assertTrue(archive_path.is_file())
            self.assertTrue(standalone_path.is_file())
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
                self.assertIn("Nindo_mud", names)
                self.assertIn("main.py", names)
                self.assertIn("commands.py", names)
                self.assertIn("legendary_items.py", names)
                self.assertIn("ui_palette.py", names)
                self.assertIn("UPDATE_INSTRUCTIONS.txt", names)
                self.assertIn("test_kage_item_colors.py", names)
                self.assertTrue(archive.read("Nindo_mud").startswith(b"#!/usr/bin/env python3"))
                self.assertEqual(archive.read("Nindo_mud"), standalone_path.read_bytes())
                self.assertIn(b"def cmd_colorscheme", archive.read("commands.py"))
                self.assertIn(b"LEGENDARY_COLOR_SCHEMES", archive.read("legendary_items.py"))
                self.assertIn(b"15.327", archive.read("changelog.py"))
                self.assertFalse(any(
                    name == "data" or name.startswith("data/") or
                    name == "world_state.json" or name == "templates.json"
                    for name in names
                ))
            # Run the exact standalone file that ships within the ZIP.
            unpacked = destination / "install"
            unpacked.mkdir()
            with ZipFile(archive_path) as archive:
                (unpacked / "Nindo_mud").write_bytes(archive.read("Nindo_mud"))
            preflight = subprocess.run(
                [sys.executable, str(unpacked / "Nindo_mud"), "--preflight"],
                cwd=unpacked, capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr[-3500:])


if __name__ == "__main__":
    unittest.main()
