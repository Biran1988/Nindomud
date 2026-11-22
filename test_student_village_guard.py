"""The four mob-24 guards share one rank-gating south-exit program."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import olc
import programs
import student_village_guard as gate
import world
from models import Player


class StudentVillageGuardTests(unittest.TestCase):
    def setUp(self):
        self.template = combat.default_template(24, "a village gate guard")
        self.templates = {24: self.template}
        self.room = world.Room(91901, "Village Gate", "The southern village gate.")
        self.south = world.Room(91902, "Road South", "The wilderness.")
        self.east = world.Room(91903, "Eastern Road", "An inner road.")
        self.room.exits.update(south=91902, east=91903)
        self.rooms = {r.vnum: r for r in (self.room, self.south, self.east)}
        self.guards = [NS(name="a village gate guard", template_vnum=24,
                          room_vnum=91901) for _ in range(4)]
        for target, attr, value in (
            (combat, "MOB_TEMPLATES", self.templates),
            (combat, "MOBS_BY_ROOM", {91901: self.guards}),
        ):
            ctx = patch.object(target, attr, value)
            ctx.start()
            self.addCleanup(ctx.stop)
        self.assertTrue(gate.install()["installed"])

    def player_session(self, rank="student", level=10, staff_level=None):
        player = Player("GuardTest", "GuardTest", level=level)
        player.village_rank = rank
        player.room_vnum = 91901
        player.stamina = 100
        account = NS(staff_level=staff_level) if staff_level else None
        session = NS(player=player, account=account, send=Mock(),
                     combat_target=None, trade=None, broadcast_room=Mock())
        return player, session

    def test_gate_is_real_move_program_and_only_installed_once(self):
        self.assertEqual(len(self.template["mob_programs"]), 1)
        prog = self.template["mob_programs"][0]
        self.assertEqual(prog["trigger"], "move")
        self.assertEqual(prog["action"], "min_rank")
        self.assertIn("south genin", prog["args"])
        self.assertEqual(programs.validate_program(
            prog["trigger"], prog["action"], prog["args"], programs.MOB_TRIGGERS), [])
        self.assertFalse(gate.install()["installed"])
        self.assertEqual(len(self.template["mob_programs"]), 1)

    def test_four_guards_block_one_student_south_with_one_message(self):
        player, session = self.player_session("student", level=10)
        with patch.object(commands.WORLD, "get", side_effect=self.rooms.get), \
             patch.object(commands.random, "randint") as roll, \
             patch.object(commands, "cmd_look") as look:
            commands.cmd_move(session, "south")
            roll.assert_not_called()
            look.assert_not_called()
        self.assertEqual(player.room_vnum, 91901)
        self.assertEqual(player.stamina, 100)
        self.assertEqual(session.send.call_count, 1)
        line = session.send.call_args.args[0]
        self.assertIn("blocks your way", line)
        self.assertIn("Genin Exam", line)

    def test_genin_at_same_level_can_exit_south(self):
        player, session = self.player_session("genin", level=10)
        with patch.object(commands.WORLD, "get", side_effect=self.rooms.get), \
             patch.object(commands.random, "randint", return_value=1), \
             patch.object(commands.olc, "_require_assigned_vnum", return_value=True), \
             patch("general_skills.before_move"), \
             patch("general_skills.broadcast_movement"), \
             patch.object(commands.combat, "follow_owner_summon"), \
             patch.object(commands, "cmd_look"), \
             patch.object(commands, "_fire_enter_triggers"), \
             patch.object(commands.groups, "follow_leader_step"):
            commands.cmd_move(session, "south")
        self.assertEqual(player.room_vnum, 91902)
        self.assertEqual(player.stamina, 99)
        self.assertNotIn("blocks your way", " ".join(
            call.args[0] for call in session.send.call_args_list))

    def test_student_can_go_east_and_all_higher_ranks_can_go_south(self):
        p, s = self.player_session("student", level=10)
        self.assertFalse(programs.check_level_gate(
            s, self.template["mob_programs"], "east"))
        for rank in ("genin", "chunin", "special jonin", "jonin"):
            p.village_rank = rank
            self.assertFalse(programs.check_level_gate(
                s, self.template["mob_programs"], "south"), rank)
        p.village_rank = "student"
        self.assertTrue(programs.check_level_gate(
            s, self.template["mob_programs"], "south"))

    def test_builder_scripts_and_saved_custom_gate_remain_untouched(self):
        previous = {"trigger": "greet", "script": "say Keep training!", "chance": 88}
        custom = {"trigger": "move", "action": "min_rank",
                  "args": "south genin Custom guard message."}
        self.template["mob_programs"] = [previous, custom]
        self.assertFalse(gate.install()["installed"])
        self.assertEqual(self.template["mob_programs"], [previous, custom])
        self.templates.clear()
        self.assertEqual(gate.install(), {"mob_exists": False, "installed": False})
        self.assertNotIn(24, self.templates)

    def test_invalid_min_rank_cannot_be_saved(self):
        self.assertTrue(programs.validate_program(
            "move", "min_rank", "south captain", programs.MOB_TRIGGERS))
        self.assertTrue(programs.validate_program(
            "greet", "min_rank", "south genin", programs.MOB_TRIGGERS))
        self.assertTrue(programs.validate_program(
            "move", "min_rank", "nonesuch genin", programs.MOB_TRIGGERS))

    def test_existing_min_level_gate_keeps_its_behavior(self):
        p, s = self.player_session("genin", level=10)
        entry = [{"trigger": "move", "action": "min_level",
                  "args": "north 12 You are too young."}]
        self.assertTrue(programs.check_level_gate(s, entry, "north"))
        p.level = 12
        self.assertFalse(programs.check_level_gate(s, entry, "north"))


if __name__ == "__main__":
    unittest.main()
