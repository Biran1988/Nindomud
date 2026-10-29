"""Uchiha inherit either Sharingan or a guaranteed elemental release path."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import data_jutsu
import data_kekkei_genkai as kkg
import storage
from session import Session
from models import Player


class UchihaElementalFallbackTests(unittest.TestCase):
    def uchiha(self, sharingan=False, level=25):
        p = Player("UchihaTest", "UchihaTest", clan="uchiha", level=level)
        p.bloodline_id = "sharingan" if sharingan else None
        self.assertEqual(kkg.sync_uchiha_elemental_heritage(p), not sharingan)
        return p

    def test_real_character_creation_assigns_exclusive_paths(self):
        with patch.object(kkg.random, "random", return_value=0.50):
            fallback = Session._create_player("TestA", "TestA", "leaf", "ninjutsu", "uchiha")
        self.assertIsNone(fallback.bloodline_id)
        self.assertTrue(fallback.uchiha_elemental_heritage)
        self.assertIsNone(fallback.elemental_release_id)
        with patch.object(kkg.random, "random", return_value=0.49):
            eye = Session._create_player("TestB", "TestB", "leaf", "ninjutsu", "uchiha")
        self.assertEqual(eye.bloodline_id, "sharingan")
        self.assertFalse(eye.uchiha_elemental_heritage)
        self.assertIsNone(eye.elemental_release_id)

    def test_failed_sharingan_roll_sets_guaranteed_fallback(self):
        with patch.object(kkg.random, "random", return_value=0.50):
            inheritance = kkg.roll_inheritance("uchiha")
        self.assertIsNone(inheritance["bloodline_id"])
        p = self.uchiha()
        self.assertTrue(p.uchiha_elemental_heritage)
        self.assertFalse(p.bloodline_awakened)
        self.assertEqual(p.bloodline_potential, 0)
        self.assertEqual(p.bloodline_talent, 0)

    def test_every_nature_pair_receives_release_and_all_three_jutsu(self):
        for pair, release_id in kkg.ELEMENTAL_RELEASES.items():
            with self.subTest(release_id=release_id):
                first, second = sorted(pair)
                p = self.uchiha(level=24)
                p.chakra_nature = first
                p.chakra_nature_revealed = True
                self.assertFalse(kkg.has_elemental_release(p, release_id))
                self.assertIsNone(p.elemental_release_id)
                p.chakra_nature_secondary = second
                p.chakra_nature_secondary_revealed = True
                p.level = 25
                self.assertTrue(kkg.sync_elemental_release(p))
                self.assertEqual(p.elemental_release_id, release_id)
                moves = sorted((j for j in data_jutsu.JUTSU.values()
                                if j.get("kkg_gate") == release_id),
                               key=lambda j: j["level_requirement"])
                self.assertEqual([j["level_requirement"] for j in moves], [25,45,70])
                self.assertIn(moves[0]["display_name"], p.learned_skills)
                self.assertIn(moves[0]["display_name"], p.practice_exempt_skills)
                for level, count in [(45,2),(70,3)]:
                    p.level = level
                    kkg.sync_elemental_techniques(p)
                    self.assertTrue(all(j["display_name"] in p.learned_skills for j in moves[:count]))
                    self.assertTrue(all(j["display_name"] in p.practice_exempt_skills for j in moves[:count]))

    def test_sharingan_is_mutually_exclusive_even_after_staff_grant(self):
        p = self.uchiha()
        p.chakra_nature = "water"
        p.chakra_nature_secondary = "wind"
        p.chakra_nature_revealed = p.chakra_nature_secondary_revealed = True
        kkg.sync_elemental_release(p)
        self.assertEqual(p.elemental_release_id, "ice_release")
        p.bloodline_id = "sharingan"
        self.assertTrue(kkg.sync_elemental_release(p))
        self.assertFalse(p.uchiha_elemental_heritage)
        self.assertIsNone(p.elemental_release_id)
        self.assertFalse(kkg.has_elemental_release(p, "ice_release"))

    def test_existing_uchiha_migrates_on_load_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                p = Player("UchihaTest", "UchihaTest", clan="uchiha", level=25)
                p.chakra_nature = "water"
                p.chakra_nature_revealed = True
                p.chakra_nature_secondary = "wind"
                p.chakra_nature_secondary_revealed = True
                raw = p.to_dict()
                raw.pop("uchiha_elemental_heritage")
                storage.ensure_dirs()
                Path(storage.player_path(p.name)).write_text(json.dumps(raw))
                loaded = storage.load_player(p.name)
                self.assertTrue(loaded.uchiha_elemental_heritage)
                self.assertEqual(loaded.elemental_release_id, "ice_release")
                self.assertIn('"uchiha_elemental_heritage": true',
                              Path(storage.player_path(p.name)).read_text())
                again = storage.load_player(p.name)
                self.assertTrue(again.uchiha_elemental_heritage)

    def test_unchanged_sharingan_chance(self):
        self.assertEqual(kkg.CLAN_INHERITANCE["uchiha"]["sharingan"], 0.50)
        with patch.object(kkg.random, "random", return_value=0.49):
            result = kkg.roll_inheritance("uchiha")
        self.assertEqual(result["bloodline_id"], "sharingan")
        p = self.uchiha(sharingan=True)
        self.assertFalse(p.uchiha_elemental_heritage)


if __name__ == "__main__":
    unittest.main()
