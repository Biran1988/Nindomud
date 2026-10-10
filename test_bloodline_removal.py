"""Retired bloodlines stop spawning and migrate old player saves."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import data_kekkei_genkai as kkg
import storage
from models import Player


class BloodlineRemovalTests(unittest.TestCase):
    def test_hozuki_rolls_no_bloodline(self):
        self.assertNotIn("hydrification", kkg.KEKKEI_GENKAI)
        self.assertEqual(kkg.eligible_kkg_for_clan("hozuki"), {})
        for _ in range(100):
            self.assertEqual(kkg.roll_inheritance("hozuki"),
                             {"bloodline_id": None, "potential": 0, "talent": 0})

    def test_legacy_holder_is_migrated_and_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                player = Player("Legacy", "Legacy")
                player.bloodline_id = "hydrification"
                player.bloodline_potential = 75
                player.bloodline_talent = 60
                player.bloodline_awakened = True
                player.bloodline_mastery = 12
                storage.save_player(player)
                loaded = storage.load_player("Legacy")
                self.assertIsNone(loaded.bloodline_id)
                self.assertEqual((loaded.bloodline_potential, loaded.bloodline_talent,
                                  loaded.bloodline_mastery), (0, 0, 0))
                self.assertFalse(loaded.bloodline_awakened)
                self.assertNotIn("hydrification", Path(storage.player_path("Legacy")).read_text())

    def test_legacy_ice_uses_natures_instead_of_clan(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                player = Player("Yuki", "Yuki")
                player.bloodline_id = "ice_release"
                player.bloodline_potential = 80
                player.chakra_nature = "wind"
                player.chakra_nature_revealed = True
                player.chakra_nature_secondary = "water"
                player.chakra_nature_secondary_revealed = True
                storage.save_player(player)
                loaded = storage.load_player("Yuki")
                self.assertIsNone(loaded.bloodline_id)
                self.assertEqual(loaded.bloodline_potential, 0)
                self.assertEqual(loaded.elemental_release_id, "ice_release")


if __name__ == "__main__":
    unittest.main()
