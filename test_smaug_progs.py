"""End-to-end checks for the Nindo_mud multiline SMAUG-style program path."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import olc
import programs
import smaug_progs
import world
from models import Player


class ScriptedProgramsTest(unittest.TestCase):
    def setUp(self):
        for target, field in ((combat, "MOB_TEMPLATES"),
                              (combat, "MOBS_BY_ROOM"),
                              (olc, "OBJECT_TEMPLATES"),
                              (world.WORLD, "rooms")):
            p = patch.object(target, field, {})
            p.start()
            self.addCleanup(p.stop)
        world.WORLD.add_room(world.Room(9001, "Academy", "Training floor."))
        world.WORLD.add_room(world.Room(9002, "Exam Hall", "A private test."))
        player = Player("Tester", "Tester", room_vnum=9001)
        player.level = 5
        player.ryo = 1000
        player.health = 50
        player.maximum_health = 100
        self.session = NS(player=player, send=Mock(), send_paginated=Mock(),
                          account=NS(name="Tester", staff_level="implementor"))
        self.session.active_sessions = lambda: [self.session]
        combat.register_template(9501, "Academy examiner", 10, 100, 2, 5, 20, 0)
        self.mob = combat.spawn_mob(9501, 9001)
        self.session.enter_editor = Mock()
        p = patch.object(olc, "_log")
        p.start()
        self.addCleanup(p.stop)

    def test_multi_action_if_else_in_one_script(self):
        script = """if level($n) < 10
 say Train more, $n!
 mpechoat The examiner denies admission.
else
 say You passed!
 mptransfer 9002
endif"""
        self.assertEqual(smaug_progs.validate_script(script), [])
        self.assertTrue(smaug_progs.execute(script, self.session, self.mob.name, self.mob))
        self.assertEqual(self.session.player.room_vnum, 9001)
        output = "\n".join(call.args[0] for call in self.session.send.call_args_list)
        self.assertIn("Train more, Tester!", output)
        self.assertIn("examiner denies admission", output)
        self.session.player.level = 10
        self.session.send.reset_mock()
        self.assertTrue(smaug_progs.execute(script, self.session, self.mob.name, self.mob))
        self.assertEqual(self.session.player.room_vnum, 9002)
        self.assertIn("You passed!", "\n".join(call.args[0] for call in self.session.send.call_args_list))

    def test_nested_if_or_else_and_variables(self):
        script = """if level($n) >= 10
  if room($n) == 9001
    say $i greets $n from $r.
  else
    mpechoat elsewhere
  endif
or rank($n) == genin
  say welcome
else
  say too young
endif"""
        # 'or' applies only to the same if, and cannot be introduced
        # after commands or nested branches have already been added.
        self.assertTrue(smaug_progs.validate_script(script))
        corrected = """if level($n) >= 10
or rank($n) == genin
  if room($n) == 9001
    say $i greets $n from $r.
  endif
else
  say too young
endif"""
        self.assertEqual(smaug_progs.validate_script(corrected), [])
        self.session.player.level = 12
        self.assertTrue(smaug_progs.execute(corrected, self.session, self.mob.name, self.mob))
        self.assertIn("9001", self.session.send.call_args_list[-1].args[0])

    def test_rejects_privileged_commands_and_unbounded_programs(self):
        for source in ["mpforce delete 100", "mpforce promoteimm Tester",
                       "exec __import__('os').system('echo hi')",
                       "mpecho hack\nendif", "if level($n) > 3\nsay bad",
                       "mptransfer -1", "mpoload 0", "mpforce admin save"]:
            self.assertTrue(smaug_progs.validate_script(source), source)
        self.assertTrue(smaug_progs.validate_script("say hello\n" * 161))
        self.assertTrue(smaug_progs.validate_script("mpecho " + "x" * 13000))

    def test_legacy_programs_and_new_scripts_run_together(self):
        t = combat.MOB_TEMPLATES[9501]
        t["mob_programs"] = [
            {"trigger": "greet", "action": "say", "args": "Welcome"},
            {"trigger": "greet", "script": "say Begin your journey, $n.",
             "chance": 100},
        ]
        programs.fire_programs(self.session, t["mob_programs"], "greet",
                               speaker_name=self.mob.name, mob=self.mob)
        out = "\n".join(call.args[0] for call in self.session.send.call_args_list)
        self.assertIn("Welcome", out)
        self.assertIn("Begin your journey, Tester.", out)

    def test_mpedit_uses_real_multiline_editor_and_saves_on_callback(self):
        olc.cmd_mpedit(self.session, ["9501", "greet"])
        self.session.enter_editor.assert_called_once()
        callback = self.session.enter_editor.call_args.args[0]
        callback("if level($n) < 10\nsay You cannot enter.\nendif")
        p = combat.MOB_TEMPLATES[9501]["mob_programs"]
        self.assertEqual(len(p), 1)
        self.assertIn("endif", p[0]["script"])
        olc.cmd_mpedit(self.session, ["9501", "#0"])
        edit_callback = self.session.enter_editor.call_args.args[0]
        edit_callback("say New dialogue.")
        self.assertEqual(p[0]["script"], "say New dialogue.")
        olc.cmd_mpstat(self.session, ["9501"])
        self.assertIn("New dialogue.", self.session.send_paginated.call_args.args[0])

    def test_invalid_save_preserves_previous_program(self):
        olc.cmd_mpedit(self.session, ["9501", "death"])
        callback = self.session.enter_editor.call_args.args[0]
        callback("mpforce promoteimm Tester")
        self.assertEqual(combat.MOB_TEMPLATES[9501]["mob_programs"], [])
        self.assertIn("not saved", self.session.send.call_args.args[0])

    def test_mob_move_direction_and_bribe_condition(self):
        self.session._mudprog_direction = "north"
        self.assertEqual(smaug_progs.validate_script(
            "if direction($d) == north\nsay Northward!\nendif"), [])
        self.assertTrue(smaug_progs.execute(
            "if direction($d) == north\nsay Northward!\nendif",
            self.session, self.mob.name, self.mob))
        self.assertIn("Northward", self.session.send.call_args.args[0])
        self.session._mudprog_bribe = 500
        self.assertTrue(smaug_progs.execute(
            "if bribe($b) >= 500\nmpheal 20\nendif",
            self.session, self.mob.name, self.mob))
        self.assertEqual(self.session.player.health, 70)

    def test_room_and_item_multiline_editors(self):
        olc.cmd_rpedit(self.session, ["enter"])
        on_save = self.session.enter_editor.call_args.args[0]
        on_save("mpechoat The mission begins.")
        self.assertEqual(world.WORLD.rooms[9001].programs[0]["trigger"], "enter")
        olc.cmd_rpstat(self.session, [])
        self.assertIn("mission begins", self.session.send_paginated.call_args.args[0])

        olc.OBJECT_TEMPLATES[9601] = olc.default_object(9601, "Exam Scroll")
        olc.cmd_opedit(self.session, ["9601", "get"])
        on_save = self.session.enter_editor.call_args.args[0]
        on_save("say Take good care of that scroll.")
        self.assertEqual(olc.OBJECT_TEMPLATES[9601]["item_programs"][0]["trigger"], "get")
        olc.cmd_opstat(self.session, ["9601"])
        self.assertIn("Take good care", self.session.send_paginated.call_args.args[0])

    def test_give_item_and_bribe_trigger_scripts(self):
        import commands
        olc.OBJECT_TEMPLATES[9601] = olc.default_object(9601, "Exam Scroll")
        olc.OBJECT_TEMPLATES[9602] = olc.default_object(9602, "Graduation Token")
        self.session.player.inventory.append("Exam Scroll")
        combat.MOB_TEMPLATES[9501]["mob_programs"] = [
            {"trigger": "give", "script":
             "if object($o) == 9601\nmpgive 9602\nendif", "chance": 100},
            {"trigger": "bribe", "script":
             "if bribe($b) >= 500\nmpheal 20\nendif", "chance": 100},
        ]
        commands.cmd_give(self.session, ["Exam", "Scroll", "examiner"])
        self.assertNotIn("Exam Scroll", self.session.player.inventory)
        self.assertIn("Graduation Token", self.session.player.inventory)
        self.assertEqual(self.session.player.health, 50)
        commands.cmd_bribe(self.session, ["500", "examiner"])
        self.assertEqual(self.session.player.ryo, 500)
        self.assertEqual(self.session.player.health, 70)

    def test_nonblocking_wait_resumes_at_due_pulse_only(self):
        import session as session_module
        self.addCleanup(smaug_progs._PENDING.clear)
        smaug_progs._PENDING.clear()
        script = "mpechoat Start\nwait 3\nmpechoat Finish"
        self.assertEqual(smaug_progs.validate_script(script), [])
        with patch.object(smaug_progs.time, "time", return_value=1000.0), \
             patch.object(session_module, "ACTIVE_SESSIONS", [self.session]):
            self.assertTrue(smaug_progs.execute(script, self.session, self.mob.name, self.mob))
            self.assertEqual(self.session.send.call_args_list[-1].args[0], "Start")
            self.assertEqual(len(smaug_progs._PENDING), 1)
            smaug_progs.process_delayed(now=1002.0)
            self.assertEqual(self.session.send.call_args_list[-1].args[0], "Start")
            smaug_progs.process_delayed(now=1003.0)
            self.assertEqual(self.session.send.call_args_list[-1].args[0], "Finish")
            self.assertFalse(smaug_progs._PENDING)

    def test_nested_wait_and_disconnected_player_cleanup(self):
        import session as session_module
        self.addCleanup(smaug_progs._PENDING.clear)
        smaug_progs._PENDING.clear()
        text = ("if level($n) < 10\nmpechoat Before\nwait 5\n"
                "mpechoat After\nendif\nmpechoat End")
        with patch.object(smaug_progs.time, "time", return_value=1000.0), \
             patch.object(session_module, "ACTIVE_SESSIONS", [self.session]):
            self.assertTrue(smaug_progs.execute(text, self.session, self.mob.name, self.mob))
            self.assertEqual(self.session.send.call_args_list[-1].args[0], "Before")
        with patch.object(session_module, "ACTIVE_SESSIONS", []):
            smaug_progs.process_delayed(now=1005.0)
        self.assertFalse(smaug_progs._PENDING)
        self.assertEqual(self.session.send.call_args_list[-1].args[0], "Before")

    def test_hp_threshold_and_no_wander_roomflag_ifchecks(self):
        world.WORLD.rooms[9001].flags.append("no_wander")
        self.mob.health = max(1, self.mob.max_health // 4)
        script = ("if hitprcnt($i) <= 30\n"
                  "if roomflag($r, no_wander)\n"
                  "mpechoat Your boss is weakened in a protected room.\n"
                  "endif\nendif")
        self.assertEqual(smaug_progs.validate_script(script), [])
        self.assertTrue(smaug_progs.execute(script, self.session, self.mob.name, self.mob))
        self.assertIn("weakened", self.session.send.call_args.args[0])
        world.WORLD.rooms[9001].flags.remove("no_wander")
        self.session.send.reset_mock()
        self.assertTrue(smaug_progs.execute(script, self.session, self.mob.name, self.mob))
        self.session.send.assert_not_called()

    def test_wait_limits_and_sandbox_ban_invalid_commands(self):
        for script in ("wait 0", "wait 121", "mpforce reboot",
                       "mpdamage 99999", "mphealmana 0", "mpjunk 1000000"):
            self.assertTrue(smaug_progs.validate_script(script), script)

    def test_remembered_quest_flag_is_per_player_and_template_persistent(self):
        dialogue = ("if remembered($n, academy_pass)\n"
                    "mpechoat You have already passed.\n"
                    "else\n"
                    "mpechoat You passed the exam today.\n"
                    "mpremember academy_pass\n"
                    "endif")
        self.assertEqual(smaug_progs.validate_script(dialogue), [])
        self.assertTrue(smaug_progs.execute(dialogue, self.session, self.mob.name, self.mob))
        self.assertIn("passed the exam today", self.session.send.call_args_list[-1].args[0])
        self.assertIn("Tester", combat.MOB_TEMPLATES[9501]["script_memory"]["academy_pass"])
        self.session.send.reset_mock()
        self.assertTrue(smaug_progs.execute(dialogue, self.session, self.mob.name, self.mob))
        self.assertIn("already passed", self.session.send.call_args_list[-1].args[0])
        self.assertTrue(smaug_progs.execute("mpforget academy_pass", self.session,
                                            self.mob.name, self.mob))
        self.assertNotIn("Tester", combat.MOB_TEMPLATES[9501]["script_memory"]["academy_pass"])

    def test_chakra_stamina_and_nonlethal_script_damage(self):
        player = self.session.player
        player.chakra = 0
        player.stamina = 0
        player.health = 70
        self.assertEqual(smaug_progs.validate_script(
            "mphealchakra 20\nmphealstamina 10\nmpdamage 100"), [])
        self.assertTrue(smaug_progs.execute(
            "mphealmana 20\nmphealmove 10\nmpdamage 100",
            self.session, self.mob.name, self.mob))
        self.assertEqual(player.chakra, 20)
        self.assertEqual(player.stamina, 10)
        self.assertEqual(player.health, 1)

    def test_mob_entry_trigger_fires_after_real_wandering_move(self):
        import session as session_module
        self.session.player.room_vnum = 9002
        world.WORLD.rooms[9001].exits["east"] = 9002
        combat.MOB_TEMPLATES[9501]["act_flags"] = ["Npc", "Wander"]
        combat.MOB_TEMPLATES[9501]["mob_programs"] = [
            {"trigger": "entry", "script": "mpechoat $i has arrived.", "chance": 100}
        ]
        self.mob.next_wander_at = 1.0
        with patch.object(session_module, "ACTIVE_SESSIONS", [self.session]), \
             patch.object(combat, "_mob_is_being_fought", return_value=False), \
             patch.object(combat.time, "time", return_value=10000.0), \
             patch.object(combat, "_broadcast_to_room"):
            combat.process_wander()
        self.assertEqual(self.mob.room_vnum, 9002)
        self.assertIn("has arrived", self.session.send.call_args.args[0])

    def test_script_loading_and_transfer_do_not_write_prototypes(self):
        olc.OBJECT_TEMPLATES[9601] = olc.default_object(9601, "Exam Scroll")
        combat.MOB_TEMPLATES[9501]["mob_programs"] = [
            {"trigger": "speech", "keyword": "test", "script":
             "mpoload 9601\nmpmload 9501\nsay Ready, $n.", "chance": 100}
        ]
        self.assertTrue(programs.fire_speech_programs(
            self.session, combat.MOB_TEMPLATES[9501]["mob_programs"],
            "test", speaker_name=self.mob.name,
            mob_template=combat.MOB_TEMPLATES[9501], mob=self.mob))
        self.assertIn("Exam Scroll", world.WORLD.rooms[9001].ground_items)
        self.assertEqual(len(combat.mobs_in_room(9001)), 2)


if __name__ == "__main__":
    unittest.main()
