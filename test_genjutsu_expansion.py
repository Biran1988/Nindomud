"""Gameplay checks for the Genjutsu expansion and Barrier mitigation."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_handsigns
import data_jutsu
import genjutsu
import leveling
import session as session_module
import status_effects
from models import Player


class GenjutsuExpansionTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Caster", "Caster", primary_class="genjutsu", level=75)
        self.player.room_vnum = 1
        self.player.chakra = 500
        self.player.maximum_chakra = 500
        self.player.inventory = ["Kunai", "Shuriken"]
        self.session = NS(player=self.player, pending_cast=None, send=Mock(), state=session_module.State.PLAYING)
        self.session.active_sessions = lambda: [self.session]

    def test_all_21_unlock_only_for_genjutsu_and_have_handsigns(self):
        added = [key for key, entry in data_jutsu.JUTSU.items()
                 if entry["jutsu_id"].startswith("genjutsu_") and
                 key not in ("demonic illusion hell viewing technique", "narakumi", "illusion walk", "silent genjutsu")]
        self.assertEqual(len(added), 21)
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(self.player)
            ninja = Player("Ninja", "Ninja", primary_class="ninjutsu", level=75)
            leveling.sync_universal_skills(ninja)
        for key in added:
            entry = data_jutsu.JUTSU[key]
            self.assertIn(entry["display_name"], self.player.learned_skills)
            self.assertNotIn(entry["display_name"], ninja.learned_skills)
            self.assertTrue(data_handsigns.sequence_for(key), key)

    def test_henge_changes_appearance_and_releases_without_cost(self):
        target = NS(name="Teacher", room_vnum=1, health=100)
        self.player.learned_skills = ["Henge"]
        with patch.object(genjutsu, "_target_in_room", return_value=target), patch.object(commands, "has_silent_genjutsu", return_value=True):
            genjutsu.begin_cast(self.session, "henge", ["Teacher"])
        self.assertEqual(genjutsu.apparent_name(self.player), "Teacher")
        self.assertEqual(self.player.name, "Caster")
        remaining = self.player.chakra
        genjutsu.begin_cast(self.session, "henge", [])
        self.assertEqual(genjutsu.apparent_name(self.player), "Caster")
        self.assertEqual(self.player.chakra, remaining)

    def test_henge_really_waits_for_handsigns_and_checks_target_again(self):
        target = NS(name="Teacher", room_vnum=1, health=100)
        self.player.learned_skills = ["Henge"]
        start_chakra = self.player.chakra
        with patch.object(genjutsu, "_target_in_room", return_value=target), \
             patch.object(combat.world.WORLD, "get", return_value=None):
            genjutsu.begin_cast(self.session, "henge", ["Teacher"])
        self.assertIsNotNone(self.session.pending_cast)
        self.assertEqual(self.player.chakra, start_chakra)
        self.session.pending_cast.remaining_seconds = 0
        target.room_vnum = 2
        with patch.object(session_module, "ACTIVE_SESSIONS", [self.session]):
            combat.tick_pending_casts()
        self.assertEqual(genjutsu.apparent_name(self.player), "Caster")
        self.assertEqual(self.player.chakra, start_chakra)

    def test_object_illusion_and_decoy_never_create_real_items(self):
        self.player.learned_skills = ["Kokohi Arazu", "Niju Kokohi Arazu"]
        with patch.object(commands, "has_silent_genjutsu", return_value=True):
            genjutsu.begin_cast(self.session, "kokohi arazu", ["Kunai", "as", "Golden", "Scroll"])
            genjutsu.begin_cast(self.session, "niju kokohi arazu", ["Shuriken"])
        self.assertEqual(self.player.inventory, ["Kunai", "Shuriken"])
        self.assertIn("Golden Scroll", genjutsu.displayed_items(self.player))
        with patch.object(session_module, "ACTIVE_SESSIONS", [self.session]):
            self.assertEqual([d["name"] for d in genjutsu.decoys_in_room(1)], ["Shuriken"])
        for _ in range(20):
            genjutsu.tick_player(self.session)
        self.assertEqual(genjutsu.displayed_items(self.player), self.player.inventory)
        self.assertEqual(self.player.genjutsu_decoys, [])

    def test_chisei_adds_temporary_capacity_and_returns_to_normal(self):
        self.player.learned_skills = ["Chisei"]
        with patch.object(commands, "has_silent_genjutsu", return_value=True):
            genjutsu.begin_cast(self.session, "chisei", [])
        self.assertGreater(self.player.maximum_chakra, 500)
        self.assertEqual(combat._genjutsu_hit_bonus(self.player, data_jutsu.JUTSU["narakumi"]), 12)
        for _ in range(6):
            combat.tick_effects_pulse(self.session)
        self.assertEqual(self.player.maximum_chakra, 500)
        self.assertEqual(self.player.chisei_chakra_bonus, 0)
        self.assertEqual(combat._genjutsu_hit_bonus(self.player, data_jutsu.JUTSU["narakumi"]), 0)

    def test_nehan_sleeps_enemies_but_respects_safe_room(self):
        self.player.learned_skills = ["Nehan Shōja"]
        foe = combat.Mob(123, 555, "Enemy", 30, 100, 100, 1, 0, 0)
        victim = Player("Victim", "Victim", level=30)
        victim.room_vnum = 1
        victim_session = NS(player=victim, send=Mock())
        with patch.object(session_module, "ACTIVE_SESSIONS", [self.session, victim_session]), \
             patch.object(combat, "mobs_in_room", return_value=[foe]), \
             patch.object(combat.world.WORLD, "get", return_value=NS(safe=True)), \
             patch.object(genjutsu.random, "randint", return_value=1), \
             patch.object(commands, "has_silent_genjutsu", return_value=True):
            genjutsu.begin_cast(self.session, "nehan shouja", [])
        self.assertIn("asleep", foe.active_status_effects)
        self.assertNotIn("asleep", victim.active_status_effects)
        self.player.cooldowns.clear()
        foe.active_status_effects.clear()
        with patch.object(session_module, "ACTIVE_SESSIONS", [self.session, victim_session]), \
             patch.object(combat, "mobs_in_room", return_value=[foe]), \
             patch.object(combat.world.WORLD, "get", return_value=NS(safe=False)), \
             patch.object(genjutsu.random, "randint", return_value=1), \
             patch.object(commands, "has_silent_genjutsu", return_value=True):
            genjutsu.begin_cast(self.session, "nehan shouja", [])
        self.assertIn("asleep", foe.active_status_effects)
        self.assertIn("asleep", victim.active_status_effects)

    def test_barrier_reduces_actual_pvp_jutsu_damage(self):
        attacker = self.player
        attacker.learned_skills = ["Distortion Flame"]
        target = Player("Target", "Target", level=30)
        target.room_vnum = 1
        target.chakra = 500
        target_session = NS(player=target, send=Mock())
        status_effects.apply_effect(target.active_status_effects, "barrier")
        with patch.object(combat.random, "randint", side_effect=[1, 100]), \
             patch.object(combat, "roll_jutsu_damage", return_value=(20, False)), \
             patch.object(combat, "_jutsu_damage_bonus", return_value=0):
            combat.use_jutsu_on_player(self.session, "distortion flame", target_session)
        self.assertEqual(target.health, 82)
        self.assertEqual(status_effects.reduce_incoming_damage({}, 20), 20)


if __name__ == "__main__":
    unittest.main()
