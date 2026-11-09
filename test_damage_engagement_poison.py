"""Hostile damage engages combat; weapon toxins/enchantments affect the victim."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import ninja_arts
import status_effects
from models import Player


class DamageEngagementTests(unittest.TestCase):
    def setUp(self):
        self.room = 991711
        self.attacker = Player("Striker", "Striker", room_vnum=self.room,
                               primary_class="bukijutsu", health=100, chakra=200)
        self.defender = Player("Defender", "Defender", room_vnum=self.room,
                               health=100, maximum_health=100)
        self.attacker.pvp_organization = "anbu"
        self.defender.pvp_organization = "root"
        self.s = NS(player=self.attacker, send=Mock(), combat_target=None, pvp_target=None)
        self.target_s = NS(player=self.defender, send=Mock(), combat_target=None, pvp_target=None)
        self.mob = combat.Mob(991712, 991713, "the guard", 25, 300, 300,
                              self.room, 0, 0)
        self.room_patch = patch.object(combat.world.WORLD, "get", return_value=NS(safe=False))
        self.room_patch.start()
        self.addCleanup(self.room_patch.stop)

    def test_ordinary_direct_hit_engages_actual_mob(self):
        self.assertTrue(combat.engage_damage_attack(self.s, self.mob))
        self.assertIs(self.s.combat_target, self.mob)
        self.assertTrue(combat.engage_damage_attack(self.s, self.mob))
        self.assertIs(self.s.combat_target, self.mob)

    def test_pvp_damage_enters_mutual_combat(self):
        self.assertTrue(combat.engage_damage_attack(self.s, self.defender, self.target_s))
        self.assertIs(self.s.pvp_target, self.target_s)
        self.assertIs(self.target_s.pvp_target, self.s)
        self.assertTrue(combat.engage_damage_attack(self.s, self.defender, self.target_s))

    def test_safe_room_disallows_pvp_damage_engagement(self):
        with patch.object(combat.world.WORLD, "get", return_value=NS(safe=True)):
            self.assertFalse(combat.engage_damage_attack(self.s, self.defender, self.target_s))
        self.assertIsNone(self.s.pvp_target)
        self.assertIsNone(self.target_s.pvp_target)
        self.assertEqual(self.defender.health, 100)

    def test_protected_npc_and_absent_target_are_rejected(self):
        with patch.object(combat, "is_immortal_mob", return_value=True):
            self.assertFalse(combat.engage_damage_attack(self.s, self.mob))
        self.assertIsNone(self.s.combat_target)
        self.mob.room_vnum += 1
        self.assertFalse(combat.engage_damage_attack(self.s, self.mob))
        self.assertIsNone(self.s.combat_target)

    def test_landed_poison_weapon_affects_actual_mob_not_wielder(self):
        self.attacker.equipment["wielded"] = "A Basic Sword [art:poison]"
        with patch.object(ninja_arts.random, "randint", return_value=1):
            self.assertEqual(ninja_arts.weapon_hit(
                self.attacker, self.mob, 20, session=self.s), 20)
        self.assertIn("poisoned", self.mob.active_status_effects)
        self.assertEqual(self.mob.active_status_effects["poisoned"]["source"], "toxin binding")
        self.assertNotIn("poisoned", self.attacker.active_status_effects)
        self.assertIn("poisons the guard", self.s.send.call_args.args[0])

    def test_landed_poison_weapon_affects_actual_player_and_notifies_both(self):
        self.attacker.equipment["wielded"] = "A Basic Sword [art:poison]"
        with patch.object(ninja_arts.random, "randint", return_value=1):
            ninja_arts.weapon_hit(self.attacker, self.defender, 25,
                                  session=self.s, target_session=self.target_s)
        self.assertIn("poisoned", self.defender.active_status_effects)
        self.assertNotIn("poisoned", self.attacker.active_status_effects)
        self.assertIn("Defender", self.s.send.call_args.args[0])
        self.assertIn("poisoned weapon infects you", self.target_s.send.call_args.args[0])
        self.assertEqual(self.defender.active_status_effects["poisoned"]["source"],
                         "toxin binding")

    def test_no_poison_proc_or_no_damage_has_no_effect_or_messages(self):
        self.attacker.equipment["wielded"] = "A Basic Sword [art:poison]"
        with patch.object(ninja_arts.random, "randint", return_value=100):
            ninja_arts.weapon_hit(self.attacker, self.defender, 25,
                                  session=self.s, target_session=self.target_s)
        self.assertNotIn("poisoned", self.defender.active_status_effects)
        self.assertFalse(self.s.send.called)
        self.assertFalse(self.target_s.send.called)
        with patch.object(ninja_arts.random, "randint", return_value=1):
            ninja_arts.weapon_hit(self.attacker, self.defender, 0,
                                  session=self.s, target_session=self.target_s)
        self.assertNotIn("poisoned", self.defender.active_status_effects)
        self.assertFalse(self.s.send.called)
        self.assertFalse(self.target_s.send.called)

    def test_elemental_and_traditional_effects_target_pvp_victim(self):
        for binding, expected in (
            ("flaming", "burning"),
            ("frost", "off_balance"),
            ("shocking", "stunned"),
        ):
            with self.subTest(binding=binding):
                self.attacker.equipment["wielded"] = f"A Basic Sword [art:{binding}]"
                self.defender.active_status_effects.clear()
                self.s.send.reset_mock()
                self.target_s.send.reset_mock()
                with patch.object(ninja_arts.random, "randint", return_value=1):
                    ninja_arts.weapon_hit(self.attacker, self.defender, 25,
                                          session=self.s, target_session=self.target_s)
                self.assertIn(expected, self.defender.active_status_effects)
                self.assertNotIn(expected, self.attacker.active_status_effects)
                self.assertTrue(self.s.send.called)
                self.assertTrue(self.target_s.send.called)

    def test_player_poison_effect_deals_real_damage_on_tick(self):
        status_effects.apply_effect(self.defender.active_status_effects,
                                    "poisoned", source="toxin binding")
        hp = self.defender.health
        with patch.object(combat.random, "randint", return_value=3), \
             patch("general_skills.upkeep"), patch("genjutsu.tick_player"):
            combat.tick_effects_pulse(self.target_s)
        self.assertLess(self.defender.health, hp)


if __name__ == "__main__":
    unittest.main()
