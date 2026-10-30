"""Immortal wizard invisibility: WHO/WHOIS/IMMS, room, movement and access."""
import json
import tempfile
import unittest
from unittest.mock import patch

import commands
import general_skills
import session
import staff_invisibility
import storage
import world
from models import Account, Player


class WizardInvisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name, value in (
            ("ACCOUNTS_DIR", self.temp.name + "/accounts"),
            ("PLAYERS_DIR", self.temp.name + "/players"),
            ("DATA_DIR", self.temp.name),
        ):
            p = patch.object(storage, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(session, "ACTIVE_SESSIONS", [])
        p.start()
        self.addCleanup(p.stop)

        self.staff, self.staff_out = self.make("Admin", "administrator")
        self.viewer, self.viewer_out = self.make("Viewer", "player")
        storage.save_account(self.staff.account)
        self.room = world.Room(501, "Test room", "A quiet hall.")
        p = patch.object(world.WORLD, "rooms", {501: self.room})
        p.start()
        self.addCleanup(p.stop)

    def make(self, name, level):
        out = []
        s = session.Session(out.append, lambda: None)
        s.player = Player(name, name, village="leaf", room_vnum=501,
                          primary_class="ninjutsu")
        s.account = Account(name, "salt", "hash", staff_level=level)
        s.state = session.State.PLAYING
        out.clear()
        return s, out

    def test_immortal_toggle_hides_all_online_and_staff_lists(self):
        self.assertIs(commands.COMMANDS["wizinvis"], staff_invisibility.command)
        commands.cmd_who(self.viewer, [])
        self.assertIn("Admin", "".join(self.viewer_out))
        self.viewer_out.clear()
        commands.dispatch(self.staff, "wizinvis", ["on"])
        self.assertTrue(self.staff.player.wizinvis)
        self.assertTrue(json.loads(open(storage.player_path("Admin")).read())["wizinvis"])
        commands.cmd_who(self.viewer, [])
        self.assertNotIn("Admin", "".join(self.viewer_out))
        self.viewer_out.clear()
        commands.cmd_whois(self.viewer, ["Admin"])
        self.assertIn("No player named", "".join(self.viewer_out))
        self.viewer_out.clear()
        commands.cmd_imms(self.viewer, [])
        self.assertNotIn("Admin", "".join(self.viewer_out))
        commands.dispatch(self.staff, "wizinvis", ["off"])
        self.assertFalse(self.staff.player.wizinvis)
        self.viewer_out.clear()
        commands.cmd_who(self.viewer, [])
        self.assertIn("Admin", "".join(self.viewer_out))

    def test_normal_player_cannot_enable(self):
        staff_invisibility.command(self.viewer, ["on"])
        self.assertFalse(self.viewer.player.wizinvis)
        self.assertIn("Only immortals", "".join(self.viewer_out))

    def test_look_and_movement_cannot_reveal_wizard_invisible(self):
        staff_invisibility.command(self.staff, ["on"])
        self.viewer_out.clear()
        with patch.object(commands.combat, "mobs_in_room", return_value=[]):
            commands.cmd_look(self.viewer, [])
        self.assertNotIn("Admin", "".join(self.viewer_out))
        self.viewer_out.clear()
        with patch.object(commands.combat, "mobs_in_room", return_value=[]):
            commands.cmd_look(self.viewer, ["admin"])
        self.assertIn("don't see", "".join(self.viewer_out))
        self.viewer_out.clear()
        general_skills.broadcast_movement(self.staff, "Admin leaves north.")
        self.assertNotIn("Admin", "".join(self.viewer_out))

    def test_other_immortals_cannot_see_hidden_staff(self):
        other, output = self.make("Other", "implementor")
        staff_invisibility.command(self.staff, ["on"])
        commands.cmd_who(other, [])
        self.assertNotIn("Admin", "".join(output))
        self.assertTrue(staff_invisibility.hidden_player(other.player, self.staff.player))

    def test_toggle_status_and_reject_bad_option(self):
        staff_invisibility.command(self.staff, ["status"])
        self.assertIn("OFF", "".join(self.staff_out))
        staff_invisibility.command(self.staff, ["nope"])
        self.assertIn("Usage", "".join(self.staff_out))
        self.assertFalse(self.staff.player.wizinvis)


if __name__ == "__main__":
    unittest.main()
