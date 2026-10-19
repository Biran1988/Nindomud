"""Persistent administrator 256-color live room theme regression tests."""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import colors
import commands
import combat
import storage
import ui_palette
import world
from models import Player


class LiveGlobalColorSchemeTests(unittest.TestCase):
    def setUp(self):
        self.original = ui_palette.current()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data_patch = patch.object(storage, "DATA_DIR", self.tmp.name)
        data_patch.start()
        self.addCleanup(data_patch.stop)
        for thing, attr in ((world.WORLD, "rooms"), (combat, "MOBS_BY_ROOM")):
            p = patch.object(thing, attr, {})
            p.start()
            self.addCleanup(p.stop)
        room = world.Room(9301, "Academy Hallway",
                          "A long wooden hallway runs through the academy.")
        room.exits["north"] = 9302
        world.WORLD.add_room(room)
        world.WORLD.add_room(world.Room(9302, "Classroom", "Students sit at desks."))
        self.player = Player("Tester", "Tester", room_vnum=9301)
        self.account = NS(staff_level="administrator")
        self.session = NS(player=self.player, account=self.account, send=Mock())
        self.session.active_sessions = lambda: [self.session]
        ui_palette._apply(ui_palette.DEFAULT_SCHEME)
        self.addCleanup(lambda: ui_palette._apply(self.original))

    def screen(self):
        return "\n".join(call.args[0] for call in self.session.send.call_args_list)

    def test_administrator_changes_live_colors_and_looks_immediately(self):
        commands.dispatch(self.session, "colorscheme", ["name", "45"])
        self.assertEqual(ui_palette.ROOM_TITLE, "&[45]")
        self.assertIn("&[45]Academy Hallway&x", self.screen())
        commands.dispatch(self.session, "colorscheme", ["desc", "230"])
        self.assertEqual(ui_palette.ROOM_DESCRIPTION, "&[230]")
        self.assertIn("&[230]A long wooden hallway", self.screen())
        commands.dispatch(self.session, "colorscheme", ["exits", "110"])
        self.assertEqual(ui_palette.EXIT_COLOR, "&[110]")
        self.assertIn("&[110]North&x", self.screen())
        self.assertIn("&[110]Exits:&x", self.screen())
        self.assertIn("\\x1b[38;5;110m", colors.render(self.screen(), True).encode("unicode_escape").decode())

    def test_atomic_persistence_across_restart_including_three_field_set(self):
        commands.cmd_colorscheme(self.session, ["set", "208", "223", "&[117]"])
        path = os.path.join(self.tmp.name, "color_scheme.json")
        with open(path, encoding="utf-8") as file:
            stored = json.load(file)
        self.assertEqual((stored["name"], stored["desc"], stored["exits"]), (208, 223, 117))
        self.assertEqual(stored["version"], 1)
        ui_palette._apply({"name": 100, "desc": 101, "exits": 102})
        self.assertTrue(ui_palette.load())
        self.assertEqual(ui_palette.current(), {"name": 208, "desc": 223, "exits": 117})

    def test_all_players_see_global_theme_on_next_look(self):
        commands.cmd_colorscheme(self.session, ["set", "220", "231", "81"])
        another = NS(player=Player("Second", "Second", room_vnum=9301),
                     account=NS(staff_level="player"), send=Mock())
        another.active_sessions = lambda: [another]
        commands.cmd_look(another, [])
        printed = another.send.call_args.args[0]
        self.assertIn("&[220]Academy Hallway", printed)
        self.assertIn("&[231]A long wooden hallway", printed)
        self.assertIn("&[81]North", printed)

    def test_player_and_builder_cannot_use_command_or_change_file(self):
        path = os.path.join(self.tmp.name, "color_scheme.json")
        for role in ("player", "helper", "builder", "area leader"):
            self.account.staff_level = role
            self.session.send.reset_mock()
            commands.dispatch(self.session, "colorscheme", ["name", "44"])
            self.assertIn("Only administrators", self.screen())
            self.assertFalse(os.path.exists(path))
            self.assertEqual(ui_palette.current(), ui_palette.DEFAULT_SCHEME)
        self.account.staff_level = "implementor"
        commands.dispatch(self.session, "colorscheme", ["name", "44"])
        self.assertEqual(ui_palette.current()["name"], 44)

    def test_invalid_colors_do_not_write_or_change_active_palette(self):
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "color_scheme.json")))
        for token in ("-1", "256", "blue", "1;DROP", "1000", "&[300]"):
            commands.cmd_colorscheme(self.session, ["name", token])
            self.assertEqual(ui_palette.current(), ui_palette.DEFAULT_SCHEME)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "color_scheme.json")))

    def test_failed_save_preserves_previous_colors_and_valid_file(self):
        commands.cmd_colorscheme(self.session, ["name", "114"])
        old = ui_palette.current()
        path = os.path.join(self.tmp.name, "color_scheme.json")
        with open(path, "rb") as f:
            saved = f.read()
        with patch.object(ui_palette, "_write_atomic", side_effect=OSError("disk full")):
            commands.cmd_colorscheme(self.session, ["name", "125"])
        self.assertEqual(ui_palette.current(), old)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), saved)
        self.assertIn("save failed", self.screen())

    def test_reset_autosaves_and_survives_restart(self):
        commands.cmd_colorscheme(self.session, ["set", "45", "48", "50"])
        commands.cmd_colorscheme(self.session, ["reset"])
        self.assertEqual(ui_palette.current(), ui_palette.DEFAULT_SCHEME)
        self.assertIn("&GNorth&x", self.screen())
        ui_palette._apply({"name": 100, "desc": 101, "exits": 102})
        self.assertTrue(ui_palette.load())
        self.assertEqual(ui_palette.current(), ui_palette.DEFAULT_SCHEME)

    def test_corrupt_file_does_not_replace_known_usable_palette(self):
        commands.cmd_colorscheme(self.session, ["set", "209", "230", "72"])
        os.unlink(os.path.join(self.tmp.name, "color_scheme.json"))
        with open(os.path.join(self.tmp.name, "color_scheme.json"), "w", encoding="utf-8") as f:
            f.write('{"name": 300, "desc": "unsafe"}')
        self.assertFalse(ui_palette.load())
        self.assertEqual(ui_palette.current(), {"name": 209, "desc": 230, "exits": 72})

    def test_room_builder_content_never_modified(self):
        original_room = world.WORLD.get(9301)
        stored = (original_room.name, original_room.description, dict(original_room.exits))
        commands.cmd_colorscheme(self.session, ["set", "16", "250", "129"])
        commands.cmd_look(self.session, [])
        self.assertEqual(stored, (original_room.name, original_room.description,
                                  dict(original_room.exits)))


if __name__ == "__main__":
    unittest.main()
