"""Executable deployment ZIP regression tests for the normal Nindo_mud server.

The download must be a direct ZIP of the regular multi-file Python code,
not a zip-in-zip; it includes the generated runnable single-file launcher.
"""
import ast
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
                self.assertIn("geoip/country.csv.gz", names)
                self.assertIn("geoip/README.md", names)
                self.assertIn("country_geo.py", names)
                self.assertIn("network_bans.py", names)
                self.assertIn("test_network_bans.py", names)
                self.assertIn(b"15.340", archive.read("changelog.py"))
                self.assertIn(b"15.341", archive.read("changelog.py"))
                self.assertIn(b"15.342", archive.read("changelog.py"))
                # Both launch methods must ship the same complete changelog.
                # Checking just old version markers missed stale release copies.
                current_changes = (build_release.ROOT / "changelog.py").read_bytes()
                self.assertEqual(archive.read("changelog.py"), current_changes)
                bundled_tree = ast.parse(archive.read("Nindo_mud").decode("utf-8"))
                bundled_sources = next(
                    ast.literal_eval(node.value)
                    for node in bundled_tree.body
                    if isinstance(node, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == "_SOURCES"
                        for target in node.targets
                    )
                )
                self.assertEqual(bundled_sources["changelog"], current_changes.decode("utf-8"))
                for version in range(343, 354):
                    self.assertIn(f'"15.{version}"'.encode(), current_changes)
                self.assertIn(b"def focused_accuracy", archive.read("general_skills.py"))
                self.assertIn("general_skills.py", names)
                self.assertIn("test_general_skills.py", names)
                self.assertIn(b"def concealed_from", archive.read("general_skills.py"))
                for skill in (b"camouflage", b"silent movement", b"sensory detect", b"focused mind"):
                    self.assertIn(skill, archive.read("data_jutsu.py"))
                self.assertNotIn("data/network_bans.json", names)
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
            # Exercise the player-facing command from the actual download.
            changes_check = (
                "import changelog, commands; "
                "from types import SimpleNamespace; "
                "messages=[]; "
                "commands.cmd_changes(SimpleNamespace(send_paginated=messages.append), []); "
                "lines=messages[0].splitlines(); "
                "assert changelog.CHANGELOG[-1][0] in lines[1]; "
                "assert all(version in messages[0] for version, _ in changelog.CHANGELOG[-11:])"
            )
            for mode in ("", "import runpy; runpy.run_path('Nindo_mud', run_name='release_test'); "):
                changes = subprocess.run(
                    [sys.executable, "-c", mode + changes_check],
                    cwd=install, capture_output=True, text=True, timeout=45,
                )
                self.assertEqual(changes.returncode, 0, changes.stderr[-3500:])
            # The portable launcher must carry its own complete country DB,
            # even when run without any neighboring source or database files.
            standalone_install = output / "standalone"
            standalone_install.mkdir()
            executable = standalone_install / "Nindo_mud"
            executable.write_bytes((install / "Nindo_mud").read_bytes())
            lookup = subprocess.run(
                [sys.executable, "-c",
                 "import runpy; runpy.run_path('Nindo_mud', run_name='release_test'); "
                 "import country_geo; "
                 "assert country_geo.lookup('1.0.0.1') == 'AU'; "
                 "assert country_geo.lookup('105.112.0.1') == 'NG'; "
                 "assert country_geo.lookup('2606:4700:4700::1111')"],
                cwd=standalone_install, capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(lookup.returncode, 0, lookup.stderr[-3500:])


if __name__ == "__main__":
    unittest.main()
