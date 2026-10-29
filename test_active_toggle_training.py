"""Live maintained effects train over time, respecting upkeep and normal gates."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import combat
import general_skills
import hidden_mist
import status_effects
import upkeep_reports
import world
from models import Player


class ActiveToggleTrainingTests(unittest.TestCase):
    def session(self, skill):
        p = Player("ToggleLearner", "ToggleLearner", level=50, village_rank="jonin", chakra=500,
                   maximum_chakra=500, primary_class="ninjutsu", chakra_nature="water")
        p.learned_skills = [skill]
        p.skill_proficiencies[skill] = 50
        p.practice_gate_enabled = True
        p.practiced_skills = [skill]
        return NS(player=p, account=NS(staff_level="player"), send=Mock(),
                  pending_cast=None, combat_target=None, pvp_target=None, broadcast_room=Mock())

    def test_each_additional_toggle_trains_only_at_intervals_and_awards_xp(self):
        for effect, skill in [*upkeep_reports.ACTIVE_EFFECT_SKILLS.items(), (None, "Chokkan")]:
            with self.subTest(skill=skill):
                s = self.session(skill)
                if effect:
                    status_effects.apply_effect(s.player.active_status_effects, effect)
                else:
                    s.player.chokkan_active = True
                with patch.object(upkeep_reports.time, "monotonic") as clock, \
                     patch.object(upkeep_reports.random, "randint", return_value=1) as roll:
                    clock.return_value = 0
                    upkeep_reports.tick_active_toggles(s)
                    clock.return_value = 9
                    upkeep_reports.tick_active_toggles(s)
                    roll.assert_not_called()
                    clock.return_value = 10
                    upkeep_reports.tick_active_toggles(s)
                    upkeep_reports.tick_active_toggles(s)
                    self.assertEqual(s.player.skill_proficiencies[skill], 51)
                    self.assertEqual(s.player.experience, 10)
                    self.assertIn("+10 experience", s.send.call_args.args[0])
                    roll.assert_called_once()
                    # Ending the effect discards the elapsed interval.
                    s.player.active_status_effects.clear()
                    s.player.chokkan_active = False
                    upkeep_reports.tick_active_toggles(s)
                    clock.return_value = 1000
                    if effect:
                        status_effects.apply_effect(s.player.active_status_effects, effect)
                    else:
                        s.player.chokkan_active = True
                    upkeep_reports.tick_active_toggles(s)
                    self.assertEqual(s.player.skill_proficiencies[skill], 51)

    def test_practice_failure_chance_and_cap_apply_to_maintenance(self):
        s = self.session("Chokkan")
        s.player.chokkan_active = True
        s.player.practiced_skills.clear()
        with patch.object(upkeep_reports.random, "randint", return_value=1) as roll:
            upkeep_reports.tick_active_toggles(s)
            roll.assert_not_called()
        s.player.practiced_skills = ["Chokkan"]
        with patch.object(upkeep_reports.time, "monotonic") as clock, \
             patch.object(upkeep_reports.random, "randint", return_value=100):
            clock.return_value = 0
            upkeep_reports.tick_active_toggles(s)
            clock.return_value = 10
            upkeep_reports.tick_active_toggles(s)
        self.assertEqual(s.player.skill_proficiencies["Chokkan"], 50)
        s.player.skill_proficiencies["Chokkan"] = 99
        with patch.object(upkeep_reports.time, "monotonic", return_value=20), \
             patch.object(upkeep_reports.random, "randint", return_value=1) as roll:
            upkeep_reports.tick_active_toggles(s)
            upkeep_reports.tick_active_toggles(s)
            roll.assert_called_once()
        self.assertEqual(s.player.skill_proficiencies["Chokkan"], 100)
        self.assertEqual(s.player.experience, 10)

    def test_mist_trains_remote_owner_only_while_paid(self):
        s = self.session("Hidden Mist Jutsu")
        room = world.Room(998870, "Mist", "Mist clearing")
        s.player.room_vnum = room.vnum
        with patch.object(world.WORLD, "rooms", {room.vnum: room}), \
             patch.object(upkeep_reports.time, "monotonic") as mono, \
             patch.object(hidden_mist.time, "time") as wall, \
             patch.object(upkeep_reports.random, "randint", return_value=1), \
             patch.object(combat, "grow_skill_from_usage"):
            mono.return_value = 0
            wall.return_value = 100
            self.assertTrue(hidden_mist.cast(s))
            s.player.room_vnum = 1
            mono.return_value = 5
            wall.return_value = 105
            hidden_mist.process_rooms([s])
            self.assertEqual(s.player.skill_proficiencies["Hidden Mist Jutsu"], 50)
            mono.return_value = 10
            wall.return_value = 110
            hidden_mist.process_rooms([s])
            self.assertEqual(s.player.skill_proficiencies["Hidden Mist Jutsu"], 51)
            self.assertEqual(s.player.experience, 10)
            s.player.chakra = 0
            mono.return_value = 20
            wall.return_value = 120
            hidden_mist.process_rooms([s])
            self.assertFalse(hidden_mist.room_active(room))
            self.assertEqual(s.player.skill_proficiencies["Hidden Mist Jutsu"], 51)

    def test_camouflage_persists_and_pays_one_chakra_per_five_seconds(self):
        s = self.session("Camouflage")
        with patch.object(general_skills.time, "time", return_value=100), \
             patch.object(combat, "grow_skill_from_usage"):
            general_skills.activate(s, "camouflage", ["on"])
        before = s.player.chakra
        for _ in range(1000):
            status_effects.tick_effects(s.player.active_status_effects)
        self.assertTrue(general_skills.active(s.player, "camouflage"))
        with patch.object(general_skills.time, "time", return_value=104):
            general_skills.upkeep(s)
        self.assertEqual(s.player.chakra, before)
        with patch.object(general_skills.time, "time", return_value=105):
            general_skills.upkeep(s)
            general_skills.upkeep(s)
        self.assertEqual(s.player.chakra, before - 1)
        s.player.chakra = 0
        with patch.object(general_skills.time, "time", return_value=110):
            general_skills.upkeep(s)
        self.assertFalse(general_skills.active(s.player, "camouflage"))
        self.assertIn("visible", s.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
