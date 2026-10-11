"""Vital Surge restores the caster safely, pays costs, and migrates old saves."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import data_jutsu
import help_system
from models import Player
import six_paths
import storage

KEY = "six paths vital surge"
NAME = "Six Paths Vital Surge"

class VitalSurgeTests(unittest.TestCase):
    def setUp(self):
        self.p = Player("Ashura", "Ashura", level=75, reincarnation="ashura",
                        health=400, maximum_health=1000, stamina=200, maximum_stamina=800,
                        chakra=1000, maximum_chakra=1000, six_paths_active=True)
        six_paths.sync_skills(self.p)
        self.s = NS(player=self.p, send=Mock(), broadcast_room=Mock(), pending_cast=None,
                    combat_target=object(), pvp_target=None)
        patcher = patch.object(storage, "save_player")
        self.save = patcher.start()
        self.addCleanup(patcher.stop)

    def cast(self, words=None):
        with patch("time.time", return_value=1000):
            commands.cmd_use_jutsu(self.s, KEY, words or [])

    def test_heal_clear_only_two_ailments_and_pay_real_cost_in_combat(self):
        self.p.active_status_effects = {"poisoned": {}, "weakened": {}, "blinded": {}, "barrier": {}}
        self.cast()
        self.assertEqual((self.p.health, self.p.stamina, self.p.chakra), (650, 400, 880))
        self.assertEqual(set(self.p.active_status_effects), {"blinded", "barrier"})
        self.assertEqual(self.p.cooldowns[KEY], 1120)
        self.assertTrue(self.p.six_paths_active)
        self.save.assert_called()
        self.s.broadcast_room.assert_called_once()

    def test_cannot_exceed_maximums_and_can_cleanse_at_full_resources(self):
        self.p.health, self.p.stamina = 999, 799
        self.cast(["self"])
        self.assertEqual((self.p.health, self.p.stamina), (1000, 800))
        self.p.cooldowns.clear()
        self.p.active_status_effects["poisoned"] = {}
        self.cast(["me"])
        self.assertEqual(self.p.chakra, 760)
        self.assertNotIn("poisoned", self.p.active_status_effects)

    def test_full_health_no_ailment_costs_nothing(self):
        self.p.health, self.p.stamina = 1000, 800
        self.cast()
        self.assertEqual(self.p.chakra, 1000)
        self.assertNotIn(KEY, self.p.cooldowns)

    def test_two_minute_cooldown_blocks_repeat_even_after_saving(self):
        self.cast()
        state = self.p.to_dict()
        self.cast()
        self.assertEqual(self.p.to_dict(), state)
        restored = Player.from_dict(state)
        self.s.player = restored
        self.cast()
        self.assertEqual(restored.to_dict(), state)
        with patch("time.time", return_value=1120):
            commands.cmd_use_jutsu(self.s, KEY, [])
        self.assertEqual(restored.chakra, 760)

    def test_reject_wrong_soul_level_inactive_unlearned_and_other_target(self):
        for attr, value in (("reincarnation", "indra"), ("level", 74), ("six_paths_active", False),
                            ("learned_skills", []), ("health", 0)):
            with self.subTest(attr=attr):
                previous = getattr(self.p, attr)
                setattr(self.p, attr, value)
                before = self.p.to_dict()
                self.cast()
                self.assertEqual(self.p.to_dict(), before)
                setattr(self.p, attr, previous)
        before = self.p.to_dict()
        self.cast(["another", "player"])
        self.assertEqual(self.p.to_dict(), before)

    def test_block_silence_pending_cast_and_insufficient_chakra(self):
        for effect in ("silenced", "stunned"):
            self.p.active_status_effects[effect] = {"remaining_ticks": 10}
            self.cast()
            self.assertEqual(self.p.health, 400)
            self.assertEqual(self.p.chakra, 1000)
            self.p.active_status_effects.clear()
        self.s.pending_cast = object()
        self.cast()
        self.assertEqual(self.p.chakra, 1000)
        self.s.pending_cast = None
        self.p.chakra = 119
        self.cast()
        self.assertEqual(self.p.chakra, 119)
        self.assertEqual(self.p.health, 400)

    def test_ordinary_chakra_control_discount(self):
        with patch("derived_stats.chakra_control_cost_discount_percent", return_value=25):
            self.cast()
        self.assertEqual(self.p.chakra, 910)

    def test_usage_can_raise_mastery_after_practice_cap(self):
        self.p.skill_proficiencies[NAME] = 80
        with patch("combat.random.randint", return_value=1):
            self.cast()
        self.assertGreater(self.p.skill_proficiencies[NAME], 80)

    def test_existing_saves_migrate_mastery_once_and_retire_signature(self):
        old = "Six Paths Rasenshuriken"
        self.p.learned_skills = [old, "Six Paths Sage Mode"]
        self.p.skill_proficiencies = {old: 150}
        self.p.signature_move = old
        self.p.cooldowns = {old.lower(): 1120}
        # Undo the routine save mock inside this persistence-only test.
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(storage, "DATA_DIR", tmp), \
             patch.object(storage, "ACCOUNTS_DIR", os.path.join(tmp, "accounts")), \
             patch.object(storage, "PLAYERS_DIR", os.path.join(tmp, "players")), \
             patch.object(storage, "save_player", storage_save):
            storage.save_player(self.p)
            loaded = storage.load_player(self.p.name)
            again = storage.load_player(self.p.name)
        self.assertNotIn(old, loaded.learned_skills)
        self.assertIn(NAME, loaded.learned_skills)
        self.assertEqual(loaded.skill_proficiencies[NAME], 100)
        self.assertEqual(loaded.signature_move, "")
        self.assertEqual(loaded.cooldowns[KEY], 1120)
        self.assertFalse(loaded.six_paths_active)
        self.assertEqual(loaded.learned_skills, again.learned_skills)
        self.assertEqual(loaded.skill_proficiencies, again.skill_proficiencies)

    def test_help_aliases_and_roster_match_new_art(self):
        self.assertNotIn("six paths rasenshuriken", data_jutsu.JUTSU)
        self.assertEqual(data_jutsu.match_prefix(["vital", "surge"]), (KEY, 2))
        self.assertEqual(data_jutsu.match_prefix(["six", "paths:", "vital", "surge"]), (KEY, 4))
        page = next(e for e in help_system.DEFAULT_HELP_ENTRIES if e["primary_keyword"] == KEY)
        self.assertIn("25%", page["body"])
        self.assertIn("120", page["body"])
        self.assertNotIn("<target>", page["body"])

storage_save = storage.save_player
if __name__ == "__main__":
    unittest.main()
