"""Global room-title/room-description 256-color presentation regression tests."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import colors
import commands
import combat
import ui_palette
import world
from models import Player


class GlobalRoomColorTests(unittest.TestCase):
    def setUp(self):
        for obj, attr in ((world.WORLD, "rooms"), (combat, "MOBS_BY_ROOM")):
            p = patch.object(obj, attr, {})
            p.start()
            self.addCleanup(p.stop)
        world.WORLD.add_room(world.Room(
            9301, "Academy Training Grounds", "The trees sway beside the academy."
        ))
        self.player = Player("ColorTester", "ColorTester", room_vnum=9301)
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          send=Mock())
        self.session.active_sessions = lambda: [self.session]

    def test_normal_look_applies_theme_to_all_room_names_and_descriptions(self):
        commands.cmd_look(self.session, [])
        screen = "\n".join(c.args[0] for c in self.session.send.call_args_list)
        self.assertIn("&[208]Academy Training Grounds&x", screen)
        self.assertIn("&[223]The trees sway beside the academy.&x", screen)
        # Room palette must not repaint exit/navigation UI.
        self.assertIn("&GExits: none&x", screen)
        self.assertNotIn("&C Академy", screen)

    def test_illusion_room_view_uses_the_same_two_global_colors(self):
        self.player.illusion_walk_caster = "Enemy"
        self.player.illusion_walk_real_room_vnum = 9301
        commands.cmd_look(self.session, [])
        screen = "\n".join(c.args[0] for c in self.session.send.call_args_list)
        self.assertIn("&[208]Academy Training Grounds&x", screen)
        self.assertIn("&[223]The trees sway beside the academy.&x", screen)

    def test_room_theme_does_not_change_saved_room_content(self):
        room = world.WORLD.get(9301)
        original = (room.name, room.description, list(room.flags))
        commands.cmd_look(self.session, [])
        self.assertEqual((room.name, room.description, list(room.flags)), original)
        self.assertEqual(original[:2], (
            "Academy Training Grounds", "The trees sway beside the academy."
        ))

    def test_room_palette_is_supported_by_existing_xterm_256_renderer(self):
        self.assertEqual(ui_palette.ROOM_TITLE, "&[208]")
        self.assertEqual(ui_palette.ROOM_DESCRIPTION, "&[223]")
        colored = colors.render(
            ui_palette.color_room_name("Forest") + " " +
            ui_palette.color_room_description("Quiet trees."), True
        )
        self.assertIn("\x1b[38;5;208mForest", colored)
        self.assertIn("\x1b[38;5;223mQuiet trees.", colored)
        plain = colors.render(ui_palette.color_room_name("Forest"), False)
        self.assertEqual(plain, "Forest")


if __name__ == "__main__":
    unittest.main()
