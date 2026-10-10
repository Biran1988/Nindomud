"""Elemental bloodlines depend on natures and exclude clan bloodlines."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import data_kekkei_genkai as kkg
import storage
from models import Player


def character(first, second=None, third=None, clan_bloodline=None):
    player = Player("Tester", "Tester")
    player.bloodline_id = clan_bloodline
    player.chakra_nature = first
    player.chakra_nature_revealed = True
    player.chakra_nature_secondary = second
    player.chakra_nature_secondary_revealed = bool(second)
    player.chakra_nature_tertiary = third
    player.chakra_nature_tertiary_revealed = bool(third)
    return player


class ElementalReleaseTests(unittest.TestCase):
    def test_every_pair_and_unmatched_pairs(self):
        for pair, expected in kkg.ELEMENTAL_RELEASES.items():
            first, second = sorted(pair)
            for a, b in ((first, second), (second, first)):
                player = character(a, b)
                self.assertTrue(kkg.sync_elemental_release(player))
                self.assertEqual(player.elemental_release_id, expected)
                self.assertFalse(kkg.sync_elemental_release(player))
        self.assertEqual(len(kkg.ELEMENTAL_RELEASES), 10)

    def test_removed_duplicate_storm_recipe_migrates(self):
        player = character("wind", "lightning")
        player.elemental_release_id = "storm_release"
        self.assertTrue(kkg.sync_elemental_release(player))
        self.assertEqual(player.elemental_release_id, "tempest_release")
        player.chakra_nature_tertiary = "water"
        player.chakra_nature_tertiary_revealed = True
        self.assertFalse(kkg.sync_elemental_release(player))
        self.assertEqual(player.elemental_release_id, "tempest_release")

    def test_clan_bloodlines_exclude_elemental_release(self):
        for inherited in ("sharingan", "byakugan", "shikotsumyaku"):
            player = character("water", "wind", clan_bloodline=inherited)
            self.assertFalse(kkg.sync_elemental_release(player))
            self.assertIsNone(player.elemental_release_id)
            player.elemental_release_id = "ice_release"
            self.assertTrue(kkg.sync_elemental_release(player))
            self.assertIsNone(player.elemental_release_id)

    def test_third_nature_upgrades_to_tota(self):
        player = character("earth", "wind")
        kkg.sync_elemental_release(player)
        self.assertEqual(player.elemental_release_id, "magnet_release")
        player.chakra_nature_tertiary = "fire"
        player.chakra_nature_tertiary_revealed = True
        self.assertTrue(kkg.sync_elemental_release(player))
        self.assertEqual(player.elemental_release_id, "dust_release")
        player.bloodline_id = "sharingan"
        self.assertTrue(kkg.sync_elemental_release(player))
        self.assertIsNone(player.elemental_release_id)

    def test_existing_revealed_natures_migrate_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                player = character("water", "wind")
                # Emulate a pre-release JSON save, without running save_player.
                storage.ensure_dirs()
                Path(storage.player_path("Tester")).write_text(__import__("json").dumps(player.to_dict()))
                loaded = storage.load_player("Tester")
                self.assertEqual(loaded.elemental_release_id, "ice_release")
                self.assertIn('"elemental_release_id": "ice_release"',
                              Path(storage.player_path("Tester")).read_text())


if __name__ == "__main__":
    unittest.main()
