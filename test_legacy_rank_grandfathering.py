"""One-time grandfathering of pre-cap player saves, without exam bypasses."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import kage
import leveling
import storage
from models import Player


class RankGrandfatheringTests(unittest.TestCase):
    def player(self, name="Legacy", level=60, rank="genin"):
        p = Player(name=name, account_name=name, village="leaf",
                   village_rank=rank, level=level)
        p.equipment["head"] = "A Konoha Genin Headband"
        return p

    def test_promotes_to_first_rank_covering_saved_level(self):
        examples = (
            ("student", 10, "student"),
            ("student", 11, "genin"),
            ("student", 16, "chunin"),
            ("genin", 15, "genin"),
            ("genin", 16, "chunin"),
            ("genin", 60, "chunin"),
            ("chunin", 80, "chunin"),
            ("chunin", 81, "special jonin"),
            ("chunin", 136, "jonin"),
            ("chunin", 201, "elite jonin"),
            ("special jonin", 135, "special jonin"),
            ("jonin", 200, "jonin"),
            ("jonin", 201, "elite jonin"),
            ("elite jonin", 250, "elite jonin"),
        )
        for index, (original, level, expected) in enumerate(examples):
            with self.subTest(original=original, level=level):
                p = self.player(name=f"Example{index}", level=level, rank=original)
                p.experience = 780123
                xp, hp, skills = p.experience, p.maximum_health, list(p.learned_skills)
                change = kage.grandfather_legacy_rank(p)
                self.assertEqual(p.village_rank, expected)
                self.assertEqual(change, (original, expected) if original != expected else None)
                self.assertEqual(p.experience, xp)
                self.assertEqual(p.maximum_health, hp)
                self.assertEqual(p.learned_skills, skills)
                self.assertLessEqual(level, kage.RANK_LEVEL_CAPS[p.village_rank])

    def test_staff_only_ranks_never_awarded_or_downgraded(self):
        for rank in ("village elder", "kage"):
            p = self.player(level=250, rank=rank)
            self.assertIsNone(kage.grandfather_legacy_rank(p))
            self.assertEqual(p.village_rank, rank)
        p = self.player(level=250, rank="student")
        self.assertEqual(kage.grandfather_legacy_rank(p), ("student", "elite jonin"))
        self.assertEqual(p.village_rank, "elite jonin")

    def test_graduation_mission_points_once_even_if_skipping_genin(self):
        p = self.player(level=65, rank="student")
        p.mission_points = 4
        p.mission_points_earned_total = 9
        self.assertEqual(kage.grandfather_legacy_rank(p), ("student", "chunin"))
        self.assertEqual(p.mission_points, 54)
        self.assertEqual(p.mission_points_earned_total, 59)
        self.assertEqual(p.equipment["head"], "A Konoha Chunin Headband")
        self.assertIsNone(kage.grandfather_legacy_rank(p))
        self.assertEqual(p.mission_points, 54)

    def test_existing_legacy_save_migrates_only_once(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(storage, "DATA_DIR", temp), \
                 patch.object(storage, "ACCOUNTS_DIR", os.path.join(temp, "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", os.path.join(temp, "players")):
                old = self.player(level=60, rank="genin")
                old.experience = leveling.cumulative_xp_for_level(60)
                old.skill_proficiencies["Strong Fist Style"] = 91
                storage.save_player(old)
                path = storage.player_path(old.name)
                with open(path, encoding="utf8") as handle:
                    data = json.load(handle)
                del data["rank_cap_migration_version"]
                with open(path, "w", encoding="utf8") as handle:
                    json.dump(data, handle)
                loaded = storage.load_player(old.name)
                self.assertEqual(loaded.village_rank, "chunin")
                self.assertEqual(loaded.rank_cap_migration_version, 1)
                self.assertEqual((loaded.rank_grandfathered_from,
                                  loaded.rank_grandfathered_to), ("genin", "chunin"))
                self.assertEqual(loaded.experience, old.experience)
                self.assertEqual(loaded.skill_proficiencies["Strong Fist Style"], 91)
                # The migration must never issue a second promotion on
                # subsequent saves, even after an immortal edits level/rank.
                loaded.village_rank = "genin"
                loaded.level = 60
                storage.save_player(loaded)
                again = storage.load_player(old.name)
                self.assertEqual(again.village_rank, "genin")
                self.assertEqual(again.rank_cap_migration_version, 1)

    def test_new_save_never_auto_promotes_after_immortal_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(storage, "DATA_DIR", temp), \
                 patch.object(storage, "ACCOUNTS_DIR", os.path.join(temp, "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", os.path.join(temp, "players")):
                new = self.player(name="Fresh", level=60, rank="genin")
                storage.save_player(new)
                loaded = storage.load_player(new.name)
                self.assertEqual(loaded.village_rank, "genin")
                self.assertFalse(loaded.rank_grandfathered_from)


if __name__ == "__main__":
    unittest.main()
