"""Class unlocks, persistent stances, status effects and the ambush rule."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_handsigns
import data_jutsu
import derived_stats
import leveling
from models import Player


class TaijutsuExpansionTests(unittest.TestCase):
    def test_class_specific_unlocks_for_new_and_returning_players(self):
        taijutsu = Player(name="Tai", account_name="Tai", primary_class="taijutsu", level=35)
        ninjutsu = Player(name="Nin", account_name="Nin", primary_class="ninjutsu", level=35)
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(taijutsu)
            leveling.sync_universal_skills(ninjutsu)
        for name in ("Choku Zuki", "Mae Geri", "Oi Zuki", "Sokuto", "Kumade", "Tamashiwara",
                     "Kihon Dachi", "Neko Ashi Dachi", "Sanchin Dachi"):
            self.assertIn(name, taijutsu.learned_skills)
            self.assertNotIn(name, ninjutsu.learned_skills)
        self.assertIn("Ushiro Shishou", ninjutsu.learned_skills)
        self.assertNotIn("Ushiro Shishou", taijutsu.learned_skills)
        self.assertIn("choku zuki", data_jutsu.jutsu_for_class_at_level("taijutsu", 3))
        self.assertIn("ushiro shishou", data_jutsu.jutsu_for_class_at_level("ninjutsu", 30))
        self.assertEqual(data_jutsu.match_prefix(["tamashiware", "guard"]), ("tamashiwara", 1))

    def test_stances_switch_persist_and_affect_combat_stats(self):
        player = Player(name="Tai", account_name="Tai", primary_class="taijutsu", level=35)
        player.stamina = 100
        player.learned_skills = ["Kihon Dachi", "Neko Ashi Dachi", "Sanchin Dachi"]
        session = NS(player=player, combat_target=None, pvp_target=None, send=Mock())
        base = derived_stats.compute_all(player)
        commands.cmd_use_jutsu(session, "kihon dachi", [])
        self.assertEqual(player.taijutsu_stance, "kihon dachi")
        self.assertEqual(derived_stats.damage_roll(player), base["damage_roll"] + 2)
        self.assertEqual(derived_stats.armor_class(player), base["armor_class"] - 2)
        commands.cmd_use_jutsu(session, "neko ashi dachi", [])
        self.assertEqual(player.taijutsu_stance, "neko ashi dachi")
        self.assertEqual(derived_stats.damage_roll(player), base["damage_roll"])
        self.assertEqual(derived_stats.hit_roll(player), base["hit_roll"] + 2)
        self.assertEqual(derived_stats.armor_class(player), base["armor_class"] - 4)
        restored = Player.from_dict(player.to_dict())
        self.assertEqual(restored.taijutsu_stance, "neko ashi dachi")
        session.combat_target = object()
        commands.cmd_use_jutsu(session, "sanchin dachi", [])
        self.assertEqual(player.taijutsu_stance, "neko ashi dachi")
        session.combat_target = None
        commands.cmd_use_jutsu(session, "sanchin dachi", [])
        self.assertEqual(derived_stats.damage_roll(player), base["damage_roll"] + 4)
        commands.cmd_use_jutsu(session, "sanchin dachi", [])
        self.assertEqual(player.taijutsu_stance, "")

    def test_strikes_apply_their_distinct_effects(self):
        player = Player(name="Tai", account_name="Tai", primary_class="taijutsu", level=35)
        player.village = "leaf"
        player.learned_skills = ["Kumade", "Tamashiwara"]
        player.stamina = 100
        mob = combat.Mob(1, 100, "target", 35, 1000, 1000, 1, 0, 0)
        session = NS(player=player, send=Mock())
        with patch.object(combat.random, "randint", return_value=1), \
             patch.object(combat, "roll_jutsu_damage", return_value=(30, False)), \
             patch.object(combat, "_jutsu_damage_bonus", return_value=0):
            combat.use_jutsu(session, "kumade", mob)
            self.assertIn("blinded", mob.active_status_effects)
            self.assertEqual(combat._accuracy_penalty_from_effects(mob), 25)
            combat.use_jutsu(session, "tamashiwara", mob)
            self.assertIn("bleeding", mob.active_status_effects)

    def test_ushiro_is_ninjutsu_opening_attack(self):
        player = Player(name="Nin", account_name="Nin", primary_class="ninjutsu", level=30)
        player.learned_skills = ["Ushiro Shishou"]
        player.room_vnum = 1
        player.position = "standing"
        mob = combat.Mob(1, 100, "target", 30, 100, 100, 1, 0, 0)
        session = NS(player=player, combat_target=None, pvp_target=None, pending_cast=None,
                     send=Mock())
        self.assertFalse(data_handsigns.has_handsigns(data_jutsu.JUTSU["ushiro shishou"]))
        with patch.object(combat, "find_mob", return_value=mob), \
             patch.object(combat, "start_attack") as start, \
             patch.object(combat, "use_jutsu") as use:
            mob.health = 90
            commands.cmd_use_jutsu(session, "ushiro shishou", ["target"])
            use.assert_not_called()
            mob.health = 100
            commands.cmd_use_jutsu(session, "ushiro shishou", ["target"])
            start.assert_called_once_with(session, mob)
            use.assert_called_once_with(session, "ushiro shishou", mob)
            session.combat_target = mob
            commands.cmd_use_jutsu(session, "ushiro shishou", ["target"])
            self.assertEqual(use.call_count, 1)

    def test_ushiro_opening_damage_is_increased(self):
        player = Player(name="Nin", account_name="Nin", primary_class="ninjutsu", level=30)
        player.village = "leaf"
        player.learned_skills = ["Ushiro Shishou"]
        player.chakra = 100
        mob = combat.Mob(1, 100, "target", 30, 1000, 1000, 1, 0, 0)
        session = NS(player=player, send=Mock())
        with patch.object(combat.random, "randint", return_value=1), \
             patch.object(combat, "roll_jutsu_damage", return_value=(20, False)), \
             patch.object(combat, "_jutsu_damage_bonus", return_value=0):
            combat.use_jutsu(session, "ushiro shishou", mob)
        self.assertEqual(mob.health, 970)
        self.assertLess(player.chakra, 100)


if __name__ == "__main__":
    unittest.main()
