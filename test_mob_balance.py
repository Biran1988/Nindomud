"""Balanced PvE baseline and final-level experience regression tests."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import dice
import leveling
import mob_balance
import storage
from models import Player


class MobBalanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_patch = patch.object(storage, "DATA_DIR", self.temp.name)
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.vnum = 995501
        self.room = 995502
        self.original = combat.MOB_TEMPLATES.get(self.vnum)
        self.original_room = combat.MOBS_BY_ROOM.get(self.room)
        self.addCleanup(self.restore)
        self.template = combat.default_template(self.vnum, "a test mob")
        self.template["level"] = 50
        combat.MOB_TEMPLATES[self.vnum] = self.template

    def restore(self):
        if self.original is None:
            combat.MOB_TEMPLATES.pop(self.vnum, None)
        else:
            combat.MOB_TEMPLATES[self.vnum] = self.original
        if self.original_room is None:
            combat.MOBS_BY_ROOM.pop(self.room, None)
        else:
            combat.MOBS_BY_ROOM[self.room] = self.original_room

    def test_same_level_means_same_baseline_regardless_of_legacy_dice(self):
        first = combat.spawn_mob(self.vnum, self.room)
        self.template["hit_dice"] = "1d1+999999"
        self.template["damage_dice"] = "1d1+99999"
        second = combat.spawn_mob(self.vnum, self.room)
        self.assertEqual((first.max_health, first.damage_dice),
                         (second.max_health, second.damage_dice))
        self.assertEqual(first.max_health, mob_balance.hp_for_level(50))
        expected = mob_balance.target_damage_for_level(50)
        actual = dice.average(first.damage_dice) + first.strength - 10
        self.assertLessEqual(abs(actual - expected), 2)

    def test_mset_manual_override_respects_existing_dice(self):
        self.template.update({"auto_balance": False, "hit_dice": "1d1+39",
                              "damage_dice": "1d1+3"})
        mob = combat.spawn_mob(self.vnum, self.room)
        self.assertEqual(mob.max_health, 40)
        self.assertEqual(mob.damage_dice, "1d1+3")

    def test_seasonal_template_preserves_event_boss_stats(self):
        self.template.update({"_halloween_event": True, "hit_dice": "1d1+299",
                              "damage_dice": "1d1+11"})
        mob = combat.spawn_mob(self.vnum, self.room)
        self.assertEqual((mob.max_health, mob.damage_dice), (300, "1d1+11"))

    def test_admin_can_tune_and_save_for_next_spawn(self):
        account = SimpleNamespace(staff_level="administrator")
        session = SimpleNamespace(account=account, send=Mock())
        mob_balance.cmd_mobscale(session, ["hp", "150"])
        self.assertEqual(mob_balance.settings()["hp_percent"], 150)
        self.assertTrue(os.path.isfile(os.path.join(self.temp.name, "mob_balance.json")))
        self.assertEqual(combat.spawn_mob(self.vnum, self.room).max_health,
                         (80 + 20 * 50 + 2 * 50 * 50) * 150 // 100)
        mob_balance.cmd_mobscale(session, ["preview", "50"])
        self.assertIn("Level 50", session.send.call_args.args[0])

    def test_regular_players_cannot_tune_mobs(self):
        session = SimpleNamespace(account=SimpleNamespace(staff_level="player"), send=Mock())
        mob_balance.cmd_mobscale(session, ["damage", "400"])
        self.assertEqual(mob_balance.settings()["damage_percent"], 100)
        self.assertIn("Only administrators", session.send.call_args.args[0])


class EndgameXPTests(unittest.TestCase):
    def test_everything_through_level_225_keeps_old_pace(self):
        self.assertEqual(leveling.endgame_xp_cost_percent(224), 100)
        self.assertEqual(leveling.endgame_xp_cost_percent(225), 150)
        self.assertEqual(leveling.endgame_xp_cost_percent(249), 270)
        player = Player("XPTester", "XPTester", level=224, village_rank="elite jonin")
        player.experience = leveling.cumulative_xp_for_level(224)
        gained = leveling.credited_experience(player, leveling.xp_band_for_level(224), 250)
        self.assertEqual(gained, leveling.cumulative_xp_for_level(225))

    def test_last_25_cost_more_even_when_large_reward_crosses_boundary(self):
        player = Player("BigGain", "BigGain", level=224, village_rank="elite jonin")
        player.experience = leveling.cumulative_xp_for_level(224)
        raw = leveling.xp_band_for_level(224) + leveling.xp_band_for_level(225)
        credited = leveling.credited_experience(player, raw, 250)
        self.assertGreater(credited, leveling.cumulative_xp_for_level(225))
        self.assertLess(credited, leveling.cumulative_xp_for_level(226))

    def test_reaching_250_keeps_exact_final_floor(self):
        player = Player("FinalXP", "FinalXP", level=249, village_rank="elite jonin")
        player.experience = leveling.cumulative_xp_for_level(249)
        credited = leveling.credited_experience(player, 10**15, 250)
        self.assertEqual(credited, leveling.cumulative_xp_for_level(250))


if __name__ == "__main__":
    unittest.main()
