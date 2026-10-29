"""Mental stat training, Genjutsu resistance/escape and Perception scan tests."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import genjutsu
import general_skills
import status_effects
import upkeep_reports
import world
from models import Player


class MentalAttributeTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Student", "Student", level=30, room_vnum=1)
        self.player.training_points = 12
        self.s = NS(player=self.player, send=Mock(), account=None)

    def test_three_trainable_stats_and_chakra_bonus(self):
        for words, name in ((["per"], "perception"), (["will"], "willpower"),
                            (["wil"], "willpower"), (["chakra", "control"], "chakra_control"),
                            (["cc"], "chakra_control")):
            before = getattr(self.player, name)
            old_chakra = self.player.maximum_chakra
            commands.cmd_train(self.s, words)
            self.assertEqual(getattr(self.player, name), before + 1)
            if name == "chakra_control":
                self.assertEqual(self.player.maximum_chakra, old_chakra + 10)
        self.assertEqual(self.player.training_points, 7)
        self.player.willpower = 75
        commands.cmd_train(self.s, ["wil"])
        self.assertEqual(self.player.willpower, 75)

    def test_resistance_and_escape_chances(self):
        self.assertEqual(status_effects.willpower_resist_chance(10), 0)
        self.assertEqual(status_effects.willpower_resist_chance(40), 15)
        self.assertEqual(status_effects.willpower_resist_chance(75), 30)
        self.assertEqual(status_effects.willpower_escape_chance(10), 0)
        self.assertEqual(status_effects.willpower_escape_chance(60), 10)
        self.assertEqual(status_effects.willpower_escape_chance(75), 13)
        self.player.willpower = 75
        effects = {}
        status_effects.apply_effect(effects, "asleep", source="nehan shouja", genjutsu=True)
        status_effects.apply_effect(effects, "stunned", source="physical blow")
        with patch.object(status_effects.random, "randint", return_value=1):
            self.assertTrue(status_effects.willpower_resists(self.player))
            self.assertEqual(status_effects.break_genjutsu_effects(effects, self.player), ["asleep"])
        self.assertNotIn("asleep", effects)
        self.assertIn("stunned", effects)

    def test_willpower_breaks_active_sleep_in_real_pulse(self):
        self.player.willpower = 75
        status_effects.apply_effect(self.player.active_status_effects, "asleep",
                                    source="nehan shouja", duration_override=12, genjutsu=True)
        with (patch.object(genjutsu, "tick_player"),
              patch.object(general_skills, "upkeep"),
              patch.object(upkeep_reports, "tick_active_toggles"),
              patch.object(status_effects.random, "randint", return_value=1)):
            combat.tick_effects_pulse(self.s)
        self.assertNotIn("asleep", self.player.active_status_effects)
        self.assertTrue(any("Willpower" in a.args[0] for a in self.s.send.call_args_list))

    def test_illusion_walk_breaks_without_stamina_penalty(self):
        self.player.willpower = 75
        self.player.illusion_walk_caster = "Other"
        self.player.illusion_walk_real_room_vnum = 1
        self.player.illusion_walk_range = 3
        self.player.stamina = 100
        with (patch.object(status_effects.random, "randint", return_value=1),
              patch.object(commands, "cmd_look")):
            commands.cmd_move(self.s, "north")
        self.assertIsNone(self.player.illusion_walk_caster)
        self.assertEqual(self.player.stamina, 100)

    def test_perception_scan_range_does_not_pass_closed_doors(self):
        rooms = [world.Room(99011+i, chr(65+i), "Room.") for i in range(4)]
        for r, n in zip(rooms, rooms[1:]):
            r.exits["north"] = n.vnum
        self.player.room_vnum = rooms[0].vnum
        self.player.learned_skills = ["Scan"]
        self.player.perception = 40
        self.s.active_sessions = lambda: [self.s]
        self.s.account = NS(staff_level="player")
        with (patch.object(world.WORLD, "rooms", {r.vnum: r for r in rooms}),
              patch.object(combat, "grow_skill_from_usage"),
              patch.object(combat, "mobs_in_room", return_value=[])):
            commands.cmd_scan(self.s, ["north"])
            self.assertIn("2 rooms north", self.s.send.call_args.args[0])
            self.assertNotIn("3 rooms north", self.s.send.call_args.args[0])
            self.player.perception = 65
            commands.cmd_scan(self.s, ["north"])
            self.assertIn("3 rooms north", self.s.send.call_args.args[0])
            rooms[1].exit_flags["north"] = ["door"]
            commands.cmd_scan(self.s, ["north"])
            self.assertNotIn("2 rooms north", self.s.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
