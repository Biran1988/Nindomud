"""Second nature selection is protected, persistent, and starts at level 25."""

import unittest
import tempfile
from unittest.mock import patch

import combat
import commands
import content
import data_kekkei_genkai as kkg
import element_choice
import help_system
import world
from models import Player
from session import ACTIVE_SESSIONS, Session, State


class ElementChoiceTests(unittest.TestCase):
    def setUp(self):
        self.kage = content._VILLAGE_ROOMS["leaf"]["kage"]
        self.original = world.WORLD.rooms.get(self.kage)
        world.WORLD.rooms[self.kage] = world.Room(self.kage, "Hokage Chamber", "Safe room", safe=True)
        self.old_room = world.WORLD.rooms.get(995002)
        world.WORLD.rooms[995002] = world.Room(995002, "Old Room", "Return here")
        self.messages = []
        self.session = Session(self.messages.append, lambda: None)
        self.session.state = State.PLAYING
        self.player = Player("TestIce", "TestIce", village="leaf", level=25, room_vnum=995002)
        self.player.chakra_nature = "water"
        self.player.chakra_nature_revealed = True
        self.session.player = self.player

    def tearDown(self):
        ACTIVE_SESSIONS.remove(self.session)
        for vnum, previous in ((self.kage, self.original), (995002, self.old_room)):
            if previous is None:
                world.WORLD.rooms.pop(vnum, None)
            else:
                world.WORLD.rooms[vnum] = previous

    def test_level_gate_and_protected_command_flow(self):
        self.player.level = 24
        self.assertFalse(element_choice.begin(self.session))
        self.player.level = 25
        with patch.object(element_choice.storage, "save_player") as save:
            self.assertTrue(element_choice.begin(self.session))
            self.assertEqual(self.player.room_vnum, self.kage)
            self.assertEqual(self.player.element_choice_return_room_vnum, 995002)
            self.session.handle_line("north")
            self.assertEqual(self.player.room_vnum, self.kage)
            self.assertIn("Only help and chat", "".join(self.messages))
            self.assertFalse(element_choice.handle_command(self.session, "help water"))
            with tempfile.TemporaryDirectory() as temp, patch.object(help_system, "HELP_DIR", temp):
                help_system.seed_default_help()
                self.session.handle_line("help water")
            self.assertIn("Water + Wind: Ice Release", "".join(self.messages))
            self.session.combat_target = combat.Mob(1, 1, "Bandit", 1, 100, 100, self.kage, 0, 0)
            combat.resolve_pulse(self.session)
            self.assertIsNone(self.session.combat_target)
            self.session.handle_line("choose water")
            self.assertFalse(self.player.chakra_nature_secondary_revealed)
            self.session.handle_line("choose wind")
            self.assertEqual(self.player.room_vnum, 995002)
            self.assertEqual(self.player.chakra_nature_secondary, "wind")
            self.assertEqual(self.player.elemental_release_id, "ice_release")
            self.assertIn("Ice Senbon", self.player.learned_skills)
            self.assertFalse(element_choice.pending(self.player))
            self.assertGreaterEqual(save.call_count, 2)

    def test_resume_after_reconnect_and_all_help_pairings(self):
        with patch.object(element_choice.storage, "save_player"):
            element_choice.begin(self.session)
            restored = Player.from_dict(self.player.to_dict())
            self.assertEqual(restored.element_choice_return_room_vnum, 995002)
            self.player.room_vnum = 995002  # simulate an external transfer
            element_choice.begin(self.session)
            self.assertEqual(self.player.room_vnum, self.kage)
        for nature in element_choice.ELEMENTS:
            page = next(e for e in help_system.DEFAULT_HELP_ENTRIES if e["primary_keyword"] == nature)
            for other in element_choice.ELEMENTS:
                if other != nature:
                    release = kkg.ELEMENTAL_RELEASE_NAMES[kkg.ELEMENTAL_RELEASES[frozenset((nature, other))]]
                    self.assertIn(release, page["body"])
        for name in kkg.ELEMENTAL_RELEASE_NAMES.values():
            self.assertTrue(any(e["primary_keyword"] == name.lower() for e in help_system.DEFAULT_HELP_ENTRIES))
        with tempfile.TemporaryDirectory() as temp, patch.object(help_system, "HELP_DIR", temp):
            help_system.seed_default_help()
            self.assertEqual(help_system.find_by_keyword("dust release")["title"],
                             "Dust Release (Kekkei Tota)")
        self.assertEqual(commands.CHAKRA_NATURE_MIN_LEVEL, 10)
        self.assertEqual(commands.CHAKRA_NATURE_SECONDARY_MIN_LEVEL, 25)
        for jutsu in __import__("data_jutsu").JUTSU.values():
            if jutsu.get("kkg_gate") in kkg.ELEMENTAL_RELEASE_NAMES:
                self.assertGreaterEqual(jutsu["level_requirement"], kkg.ELEMENTAL_RELEASE_REVEAL_LEVEL)


if __name__ == "__main__":
    unittest.main()
