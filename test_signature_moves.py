"""Signature selection, retraining, damage/effect bonuses and persistence."""

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import leveling
import signature_moves
import upkeep_reports
import storage
import world
from models import Player


class SignatureMoveTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("SignatureTester", "SignatureTester")
        self.player.learned_skills = ["Dynamic Entry", "Mae Geri", "Kanashibari", "Barrier", "Soto Uke"]
        self.player.skill_proficiencies = {name: 100 for name in self.player.learned_skills}
        self.player.practice_points = 50
        self.session = SimpleNamespace(player=self.player, send=Mock())

    def test_requires_100_and_rejects_passives(self):
        self.player.skill_proficiencies["Dynamic Entry"] = 99
        commands.cmd_signature(self.session, ["Dynamic", "Entry"])
        self.assertFalse(self.player.signature_move)
        self.assertIn("100%", self.session.send.call_args.args[0])
        commands.cmd_signature(self.session, ["Soto", "Uke"])
        self.assertFalse(self.player.signature_move)

    def test_switch_resets_old_to_100_and_requires_new_use(self):
        commands.cmd_signature(self.session, ["Dynamic", "Entry"])
        self.assertEqual(self.player.signature_move, "Dynamic Entry")
        self.assertFalse(signature_moves.empowered(self.player, data_jutsu.JUTSU["dynamic entry"]))
        points = self.player.practice_points
        with patch.object(commands, "_find_matching_teacher", return_value=object()):
            commands.cmd_practice(self.session, ["Dynamic", "Entry"])
        self.assertEqual(self.player.skill_proficiencies["Dynamic Entry"], 100)
        self.assertEqual(self.player.practice_points, points)
        self.assertIn("through successful use", self.session.send.call_args.args[0])
        with patch.object(combat.random, "randint", return_value=1):
            for _ in range(25):
                combat.grow_skill_from_usage(self.player, "Dynamic Entry", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Dynamic Entry"], 150)
        self.assertTrue(signature_moves.empowered(self.player, data_jutsu.JUTSU["dynamic entry"]))
        combat.grow_skill_from_usage(self.player, "Dynamic Entry", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Dynamic Entry"], 150)
        commands.cmd_signature(self.session, ["Mae", "Geri"])
        self.assertEqual(self.player.skill_proficiencies["Dynamic Entry"], 100)
        self.assertEqual(self.player.signature_move, "Mae Geri")
        self.assertFalse(signature_moves.empowered(self.player, data_jutsu.JUTSU["mae geri"]))
        commands.cmd_signature(self.session, ["Dynamic", "Entry"])
        self.assertEqual(self.player.skill_proficiencies["Dynamic Entry"], 100)
        self.assertEqual(self.player.skill_proficiencies["Mae Geri"], 100)
        commands.cmd_signature(self.session, ["clear"])
        self.assertFalse(self.player.signature_move)

    def test_signature_toggle_can_grow_by_active_use_not_practice(self):
        self.player.signature_move = "Barrier"
        with patch.object(upkeep_reports.time, "monotonic", side_effect=[0, 10]), \
             patch.object(upkeep_reports.random, "randint", return_value=1):
            upkeep_reports.maintain_skill(self.player, "Barrier", session=self.session)
            upkeep_reports.maintain_skill(self.player, "Barrier", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Barrier"], 101)

    def test_other_mastered_jutsu_remains_capped_at_100(self):
        with patch.object(combat.random, "randint", return_value=1):
            combat.grow_skill_from_usage(self.player, "Mae Geri", session=self.session)
        self.assertEqual(self.player.skill_proficiencies["Mae Geri"], 100)

    def test_damage_status_and_utility_effects_only_at_150(self):
        damage = data_jutsu.JUTSU["dynamic entry"]
        effect = data_jutsu.JUTSU["kanashibari"]
        barrier = data_jutsu.JUTSU["barrier"]
        self.player.signature_move = "Dynamic Entry"
        self.assertEqual(signature_moves.amount(self.player, damage, 100), 100)
        self.player.skill_proficiencies["Dynamic Entry"] = 150
        self.assertEqual(signature_moves.amount(self.player, damage, 100), 125)
        self.assertEqual(signature_moves.amount(self.player, effect, 100), 100)
        self.player.signature_move = "Kanashibari"
        self.player.skill_proficiencies["Kanashibari"] = 150
        self.assertEqual(signature_moves.duration(self.player, effect, 10), 13)
        self.player.signature_move = "Barrier"
        self.player.skill_proficiencies["Barrier"] = 150
        self.assertEqual(signature_moves.duration(self.player, barrier, 180), 225)

    def test_saved_character_and_immortal_login_keep_signature(self):
        self.player.signature_move = "Dynamic Entry"
        self.player.skill_proficiencies["Dynamic Entry"] = 150
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(storage, "DATA_DIR", folder), patch.object(storage, "PLAYERS_DIR", folder), patch.object(storage, "ACCOUNTS_DIR", folder):
                storage.save_player(self.player)
                loaded = storage.load_player(self.player.name)
        self.assertEqual(loaded.signature_move, "Dynamic Entry")
        self.assertEqual(loaded.skill_proficiencies["Dynamic Entry"], 150)
        loaded._immortal_skill_mastery = True
        leveling.grant_immortal_jutsu(loaded)
        self.assertEqual(loaded.skill_proficiencies["Dynamic Entry"], 150)

    def test_real_mob_cast_applies_damage_and_status_bonus(self):
        self.player.signature_move = "Kanashibari"
        self.player.skill_proficiencies["Kanashibari"] = 150
        self.player.room_vnum = 91919
        self.player.chakra = self.player.maximum_chakra = 9999
        mob = combat.Mob(1, 91920, "Training Target", 1, 10000, 10000, 91919, 0, 0)
        with patch.dict(world.WORLD.rooms, {91919: world.Room(91919, "Arena", "Test.")}), \
             patch.object(combat, "_can_use_jutsu", return_value=True), \
             patch.object(combat, "roll_jutsu_damage", return_value=(100, False)), \
             patch.object(combat, "_jutsu_damage_bonus", return_value=0), \
             patch.object(combat.random, "randint", return_value=1):
            combat.use_jutsu(self.session, "kanashibari", mob)
        self.assertEqual(mob.active_status_effects["paralyzed"]["duration"], 13)
        self.assertEqual(10000 - mob.health, 125)


if __name__ == "__main__":
    unittest.main()
