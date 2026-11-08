"""Eight Inner Gates progression, combat integration and safe Battle Ready tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import battle_ready
import combat
import data_jutsu
import eight_gates
from models import Player


class EightGatesTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Guy", "Guy", primary_class="taijutsu", level=250)
        self.player.maximum_stamina = self.player.stamina = 5000
        self.player.maximum_health = self.player.health = 5000
        self.player.learned_skills.extend(row[0] for row in eight_gates.GATES)
        self.messages = []
        self.session = SimpleNamespace(
            player=self.player, send=self.messages.append,
            pending_cast=None, pending_action=None,
        )
        self.practice = patch("skill_training.needs_first_practice", return_value=False)
        self.practice.start()
        self.growth = patch("combat.grow_skill_from_usage")
        self.growth.start()

    def tearDown(self):
        self.growth.stop()
        self.practice.stop()

    def test_all_eight_gates_and_six_followups_registered_at_levels(self):
        self.assertEqual(len(eight_gates.GATES), 8)
        for index, (name, level, *_rest) in enumerate(eight_gates.GATES, 1):
            entry = data_jutsu.JUTSU[name.casefold()]
            self.assertEqual(entry["jutsu_type"], "eight_gate")
            self.assertEqual(entry["required_gate"], index)
            self.assertEqual(entry["level_requirement"], level)
            self.assertEqual(entry["class_requirement"], "taijutsu")
        for key, (required_gate, *_rest) in eight_gates.GATE_STANCES.items():
            self.assertEqual(data_jutsu.JUTSU[key]["required_gate"], required_gate)

    def test_gates_exclusive_to_taijutsu_and_practiced(self):
        self.player.primary_class = "ninjutsu"
        self.assertFalse(eight_gates.qualified(self.player, 1))
        self.player.primary_class = "taijutsu"
        with patch("skill_training.needs_first_practice", return_value=True):
            self.assertFalse(eight_gates.qualified(self.player, 1))
        self.player.level = 19
        self.assertFalse(eight_gates.qualified(self.player, 1))

    def test_gate_safe_only_activates_gate_seven(self):
        self.assertEqual(eight_gates.highest_safe(self.player), 7)
        eight_gates.command(self.session, ["safe"])
        self.assertEqual(self.player.gates_open, 7)
        self.assertLess(self.player.stamina, 5000)
        self.assertEqual(eight_gates.physical_damage(self.player, 100), 225)
        self.assertEqual(eight_gates.accuracy(self.player), 15)
        self.assertEqual(eight_gates.physical_damage(
            self.player, 100, {"class_requirement": "ninjutsu"}), 100)

    def test_early_gates_do_not_wound_higher_gates_do(self):
        eight_gates.open_gate(self.session, 3)
        before = self.player.health
        stamina = self.player.stamina
        eight_gates.tick(self.session, now=self.player.gates_last_upkeep_at + 3)
        self.assertEqual(self.player.health, before)
        self.assertEqual(self.player.stamina, stamina - eight_gates.GATES[2][3])
        eight_gates.open_gate(self.session, 7)
        before = self.player.health
        eight_gates.tick(self.session, now=self.player.gates_last_upkeep_at + 3)
        self.assertLess(self.player.health, before)

    def test_gate_eight_requires_confirmation_and_cannot_be_closed(self):
        self.assertFalse(eight_gates.open_gate(self.session, 8))
        self.assertEqual(eight_gates.active(self.player), 0)
        self.assertTrue(eight_gates.open_gate(self.session, 8, confirm=True))
        self.assertEqual(eight_gates.active(self.player), 8)
        eight_gates.command(self.session, ["off"])
        self.assertEqual(eight_gates.active(self.player), 8)
        eight_gates.tick(self.session, now=self.player.gates_eighth_expires_at + 1)
        self.assertEqual(self.player.health, 0)
        self.assertEqual(self.player.gates_open, 0)
        self.assertGreater(self.player.gates_cooldown_until, 0)

    def test_cannot_open_gate_strike_without_prerequisite_gate(self):
        for key in ("front lotus", "reverse lotus", "morning peacock",
                    "daytime tiger", "evening elephant", "night guy"):
            self.assertFalse(eight_gates.strike_unlocked(self.player, data_jutsu.JUTSU[key]))
        eight_gates.open_gate(self.session, 7)
        self.assertTrue(eight_gates.strike_unlocked(self.player, data_jutsu.JUTSU["daytime tiger"]))
        self.assertFalse(eight_gates.strike_unlocked(self.player, data_jutsu.JUTSU["night guy"]))

    def test_gate_healing_and_extra_attacks_have_real_effects(self):
        self.player.health = 4000
        eight_gates.open_gate(self.session, 2)
        self.assertEqual(self.player.health, 4250)
        self.assertEqual(eight_gates.dodge(self.player), 3)
        self.assertEqual(eight_gates.extra_attacks(self.player), 0)
        eight_gates.open_gate(self.session, 3)
        self.assertEqual(eight_gates.extra_attacks(self.player), 1)
        eight_gates.open_gate(self.session, 7)
        self.assertEqual(eight_gates.extra_attacks(self.player), 2)
        self.assertEqual(eight_gates.dodge(self.player), 14)

    def test_gate_eight_stamina_exhaustion_still_defeats_caster(self):
        eight_gates.open_gate(self.session, 8, confirm=True)
        self.player.stamina = 0
        eight_gates.tick(self.session, now=self.player.gates_last_upkeep_at + 3)
        self.assertEqual(eight_gates.active(self.player), 0)
        self.assertEqual(self.player.health, 0)

    def test_eighth_gate_state_survives_save_restore(self):
        eight_gates.open_gate(self.session, 8, confirm=True)
        restored = Player.from_dict(self.player.to_dict())
        self.assertEqual(restored.gates_open, 8)
        self.assertEqual(restored.gates_eighth_expires_at,
                         self.player.gates_eighth_expires_at)

    def test_battle_ready_opt_in_never_selects_gate_eight(self):
        self.assertFalse(battle_ready.settings(self.player)["eight gates"])
        self.player.battle_ready_settings["eight gates"] = True
        with patch.object(eight_gates, "command") as cmd:
            battle_ready._cast(self.session, "eight gates")
        cmd.assert_called_once_with(self.session, ["safe"])
        self.assertEqual(eight_gates.highest_safe(self.player), 7)


if __name__ == "__main__":
    unittest.main()
