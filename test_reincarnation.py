"""Birth rarity, permanent heritage, attribute grants and resource growth."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

import commands
import config
import data_clans
import help_system
import leveling
from models import Player
import reincarnation as souls
from session import Session
import storage


class ReincarnationTests(unittest.TestCase):
    def create(self, clan="uchiha", roll=0, primary_class="ninjutsu"):
        village = next(village for village, clans in data_clans.CLANS_BY_VILLAGE.items() if clan in clans)
        with patch.object(souls.secrets, "randbelow", return_value=roll):
            return Session._create_player("Reborn", "Reborn", village, primary_class, clan)

    def test_exactly_one_winning_face_of_100_for_each_supported_lineage(self):
        for clan, expected in souls.LINEAGES.items():
            hits = 0
            for face in range(100):
                p = Player("Test", "Test", clan=clan, reincarnation_roll_complete=False)
                with patch.object(souls.secrets, "randbelow", return_value=face) as roll:
                    result = souls.assign_at_creation(p)
                    roll.assert_called_once_with(100)
                hits += bool(result)
                self.assertEqual(result, expected if face == 0 else "")
                self.assertTrue(p.reincarnation_roll_complete)
                self.assertEqual(p.reincarnation_birth_clan, clan)
            self.assertEqual(hits, 1)

    def test_unrelated_clans_and_legacy_records_never_roll(self):
        for clan in set(data_clans.CLANS) - souls.LINEAGES.keys() - {"none"}:
            with patch.object(souls.secrets, "randbelow") as roll:
                p = self.create(clan)
                self.assertFalse(p.reincarnation)
                roll.assert_not_called()
        raw = Player("Legacy", "Legacy", clan="uchiha").to_dict()
        for key in list(raw):
            if key.startswith("reincarnation"):
                raw.pop(key)
        p = Player.from_dict(raw)
        with patch.object(souls.secrets, "randbelow") as roll:
            self.assertEqual(souls.assign_at_creation(p), "")
            roll.assert_not_called()

    def test_creation_grants_five_to_every_attribute_for_both_souls_and_all_classes(self):
        for clan in souls.LINEAGES:
            for class_key in ("ninjutsu", "genjutsu", "taijutsu", "bukijutsu"):
                with self.subTest(clan=clan, primary_class=class_key):
                    normal = self.create(clan, 1, class_key)
                    rare = self.create(clan, 0, class_key)
                    for attribute in souls.STARTING_ATTRIBUTES:
                        self.assertEqual(getattr(rare, attribute), getattr(normal, attribute) + 5, attribute)
                    snapshot = rare.to_dict()
                    souls.assign_at_creation(rare)
                    souls.grant_starting_perks(rare)
                    self.assertEqual(rare.to_dict(), snapshot)

    def test_correct_starting_resources_and_no_extra_bloodline_grants(self):
        with patch("data_kekkei_genkai.roll_inheritance",
                   return_value={"bloodline_id": None, "potential": 0, "talent": 0}):
            indra = self.create()
            ashura = self.create("senju")
        self.assertEqual((indra.maximum_health, indra.maximum_chakra, indra.maximum_stamina),
                         (config.STARTING_HEALTH, config.STARTING_CHAKRA + config.STARTING_CHAKRA // 10,
                          config.STARTING_STAMINA))
        self.assertEqual((ashura.maximum_health, ashura.maximum_chakra, ashura.maximum_stamina),
                         (config.STARTING_HEALTH * 11 // 10, config.STARTING_CHAKRA,
                          config.STARTING_STAMINA * 11 // 10))
        self.assertIsNone(indra.bloodline_id)
        self.assertIsNone(ashura.bloodline_id)

    def test_level_growth_uses_raised_attributes_and_exact_fraction_carry(self):
        for clan in souls.LINEAGES:
            p = self.create(clan)
            control = Player.from_dict(p.to_dict())
            control.reincarnation = ""
            initial = {r: getattr(p, "maximum_" + r) for r in ("health", "chakra", "stamina")}
            carries = dict(p.reincarnation_growth_carry)
            for character in (p, control):
                character.village_rank = "genin"  # Level 10 Academy cap now requires graduation.
                leveling.grant_experience(character, leveling.cumulative_xp_for_level(11))
            self.assertEqual(p.level, 11)
            for r, start in initial.items():
                normal_gain = getattr(control, "maximum_" + r) - start
                bonus = (normal_gain * 10 + carries.get(r, 0)) // 100 if r in souls.BONUS_RESOURCES[p.reincarnation] else 0
                self.assertEqual(getattr(p, "maximum_" + r), start + normal_gain + bonus)
                self.assertEqual(getattr(p, r), getattr(p, "maximum_" + r))

    def test_save_reload_and_clan_change_keep_soul_stats_and_fraction_carry(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(storage, "DATA_DIR", tmp), \
                patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
            p = self.create()
            messages = []
            s = SimpleNamespace(player=p, send=messages.append)
            commands.cmd_clan(s, ["join", "senju"])
            self.assertEqual(p.clan, "senju")
            self.assertEqual(p.reincarnation_birth_clan, "uchiha")
            storage.save_player(p)
            with patch.object(souls.secrets, "randbelow") as roll:
                loaded = storage.load_player(p.name)
                souls.assign_at_creation(loaded)
                souls.grant_starting_perks(loaded)
                roll.assert_not_called()
            self.assertEqual(loaded.reincarnation, "indra")
            for attr in souls.STARTING_ATTRIBUTES:
                self.assertEqual(getattr(loaded, attr), getattr(p, attr))
            self.assertEqual(loaded.maximum_chakra, p.maximum_chakra)
            self.assertEqual(loaded.reincarnation_growth_carry, p.reincarnation_growth_carry)
            for character in (p, loaded):
                leveling.grant_experience(character, leveling.cumulative_xp_for_level(5))
            self.assertEqual(p.maximum_chakra, loaded.maximum_chakra)
            self.assertEqual(p.reincarnation_growth_carry, loaded.reincarnation_growth_carry)

    def test_failed_roll_is_final_even_after_joining_an_eligible_clan(self):
        p = self.create("uzumaki", roll=99)
        p.clan = "uchiha"
        with patch.object(souls.secrets, "randbelow") as roll:
            souls.assign_at_creation(p)
            souls.grant_starting_perks(p)
            roll.assert_not_called()
        self.assertEqual(p.reincarnation, "")
        self.assertEqual(p.reincarnation_birth_clan, "uzumaki")

    def test_score_status_and_help_explain_the_actual_perks(self):
        p = self.create("uzumaki")
        self.assertIn("Ashura", "\n".join(commands.build_score_lines(p, "Nobody")))
        messages = []
        commands.COMMANDS["reincarnation"](SimpleNamespace(player=p, send=messages.append), [])
        self.assertIn("+5", messages[-1])
        self.assertIn("Health/Stamina", messages[-1])
        page = next(e for e in help_system.DEFAULT_HELP_ENTRIES if e["primary_keyword"] == "reincarnation")
        self.assertIn("1% total", page["body"])
        self.assertIn("+5", page["body"])


if __name__ == "__main__":
    unittest.main()
