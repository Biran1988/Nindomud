"""Executable deployment ZIP regression tests for the normal Nindo_mud server.

The download must be a direct ZIP of the regular multi-file Python code,
not a zip-in-zip; it includes the generated runnable single-file launcher.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts import build_release


class ReleaseArchiveTests(unittest.TestCase):
    def test_normal_zip_contains_current_source_executable_and_no_saved_data(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            build_release.build(output)
            archive_path = output / "Nindo_mud.zip"
            self.assertTrue(archive_path.is_file())
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
                self.assertIn("Nindo_mud", names)
                self.assertNotIn("Nindo_mud.zip", names)
                self.assertNotIn("UPDATE_INSTRUCTIONS.txt", names)
                for name in (
                    "main.py", "commands.py", "legendary_items.py",
                    "ui_palette.py", "test_kage_item_colors.py",
                    "changelog.py", "scripts/build_release.py",
                ):
                    self.assertIn(name, names)
                self.assertIn(b"def cmd_colorscheme", archive.read("commands.py"))
                self.assertIn(b"SLEEPING_ALLOWED_COMMANDS", archive.read("commands.py"))
                self.assertIn(b"HOSPITAL_MULTIPLIER = 10.0", archive.read("regen.py"))
                self.assertIn(b"if hospital:", archive.read("regen.py"))
                self.assertIn(b"int(normal * multiplier)", archive.read("regen.py"))
                self.assertIn("test_hospital_regen.py", names)
                self.assertIn(b"15.330", archive.read("changelog.py"))
                self.assertIn(b"if canonical == \"safe\"", archive.read("olc.py"))
                self.assertIn(b"HOSPITAL_MULTIPLIER = 10.0", archive.read("Nindo_mud"))
                self.assertIn(b"def cmd_delete(", archive.read("commands.py"))
                self.assertIn(b'10)', archive.read("commands.py"))
                self.assertIn(b"def delete_character(", archive.read("storage.py"))
                self.assertIn(b"def grow_skill_from_usage(", archive.read("combat.py"))
                self.assertIn(b"def cmd_delete(", archive.read("Nindo_mud"))
                self.assertIn(b"15.331", archive.read("changelog.py"))
                self.assertIn("test_skill_xp_and_character_delete.py", names)
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
