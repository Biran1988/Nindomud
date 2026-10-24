"""Real casts, overlapping room effects, expiry, extinguishing and room views."""
import unittest
from unittest.mock import patch

import colors
import combat
import commands
import hidden_mist
import mangekyo_mobs
import room_jutsu_objects
import world
from models import Account, Player
from session import ACTIVE_SESSIONS, Session, State


class RoomJutsuObjectTests(unittest.TestCase):
    def setUp(self):
        self.room = world.Room(992820, "Jutsu Clearing", "An open clearing.")
        self.neighbor = world.Room(992821, "Jutsu Path", "A neighboring path.")
        self.neighbor.exits["north"] = self.room.vnum
        for room in (self.room, self.neighbor):
            world.WORLD.rooms[room.vnum] = room
            self.addCleanup(world.WORLD.rooms.pop, room.vnum, None)
        self.output = []
        self.session = Session(self.output.append, lambda: None)
        self.session.player = Player("JutsuNinja", "JutsuNinja", level=100,
                                     room_vnum=self.room.vnum)
        self.session.account = Account("JutsuNinja", "salt", "hash", staff_level="implementor")
        self.session.state = State.PLAYING
        self.addCleanup(ACTIVE_SESSIONS.remove, self.session)
        self.session.player.chakra = 1000
        self.mob = combat.Mob(992820, 992820, "Test Bandit", 30, 500, 500,
                              self.room.vnum, 0, 0)
        combat.MOBS_BY_ROOM[self.room.vnum] = [self.mob]
        self.addCleanup(combat.MOBS_BY_ROOM.pop, self.room.vnum, None)
        self.output.clear()

    def output_text(self):
        text = colors.render("".join(self.output), False)
        self.output.clear()
        return text

    def test_mist_object_tracks_real_cast_and_toggle(self):
        self.assertTrue(hidden_mist.cast(self.session))
        self.output.clear()
        commands.cmd_look(self.session, [])
        text = self.output_text()
        self.assertEqual(text.count("dense hidden mist"), 1)
        self.assertLess(text.index("Test Bandit is here"), text.index("dense hidden mist"))
        commands.cmd_look(self.session, ["mist"])
        self.assertIn("A Shroud of Hidden Mist", self.output_text())
        commands.cmd_get(self.session, ["mist"])
        self.assertIn("cannot pick it up", self.output_text())
        self.assertEqual(self.room.ground_items, [])
        self.assertEqual(self.session.player.inventory, [])
        # A maintained mist has no visual expiry timer.
        with patch.object(room_jutsu_objects.time, "time", return_value=10**12):
            commands.cmd_look(self.session, [])
            self.assertIn("dense hidden mist", self.output_text())
        hidden_mist.dismiss(self.session)
        self.output.clear()
        commands.cmd_look(self.session, ["mist"])
        self.assertIn("don't see that", self.output_text())

    def test_mob_amaterasu_stays_in_room_and_vanishes_when_extinguished(self):
        mangekyo_mobs.resolve(self.session, "amaterasu", self.mob)
        self.output.clear()
        commands.cmd_look(self.session, ["black", "flames"])
        self.assertIn("The Black Flames of Amaterasu", self.output_text())
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "the black flames of amaterasu"))
        # Target movement does not remove the separate, lingering room fire.
        self.mob.room_vnum = self.neighbor.vnum
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "amaterasu"))
        self.assertIsNone(room_jutsu_objects.find(self.neighbor, "amaterasu"))
        mangekyo_mobs.extinguish(self.session, ["room"])
        self.assertIsNone(room_jutsu_objects.find(self.room, "amaterasu"))
        self.assertEqual(self.room.ground_items, [])

    def test_pvp_amaterasu_creates_same_room_object_and_scan_sees_it(self):
        target = Session(lambda text: None, lambda: None)
        self.addCleanup(ACTIVE_SESSIONS.remove, target)
        target.player = Player("Victim", "Victim", room_vnum=self.room.vnum)
        target.state = State.PLAYING
        combat.resolve_amaterasu_cast(self.session, target, grow_handsigns=False)
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "amaterasu"))
        self.session.player.room_vnum = self.neighbor.vnum
        self.session.player.learned_skills.append("Scan")
        self.output.clear()
        commands.cmd_scan(self.session, ["north"])
        self.assertIn("black flames of Amaterasu", self.output_text())
        with patch.object(room_jutsu_objects.time, "time", return_value=self.room.amaterasu_fire_expires_at):
            commands.cmd_scan(self.session, ["north"])
            self.assertNotIn("black flames of Amaterasu", self.output_text())

    def test_overlapping_effects_recast_and_independent_removal(self):
        self.assertTrue(hidden_mist.cast(self.session))
        mangekyo_mobs.resolve(self.session, "amaterasu", self.mob)
        mangekyo_mobs.resolve(self.session, "amaterasu", self.mob)
        self.room.kekkei_no_me_caster = "JutsuNinja"
        self.room.kekkei_no_me_element = "lightning"
        self.room.kekkei_no_me_expires_at = self.room.amaterasu_fire_expires_at
        self.room.temp_description_text = "A thick cloud of steam still hangs in the air."
        self.room.temp_description_until = self.room.amaterasu_fire_expires_at
        self.assertEqual(len(room_jutsu_objects.active_objects(self.room)), 4)
        mangekyo_mobs.extinguish(self.session, ["all"])
        self.assertEqual(len(room_jutsu_objects.active_objects(self.room)), 3)
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "mist"))
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "lightning domain"))
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "steam"))
        self.room.hidden_mist_caster = None
        self.room.kekkei_no_me_caster = None
        self.room.temp_description_text = ""
        self.assertEqual(room_jutsu_objects.active_objects(self.room), [])


if __name__ == "__main__":
    unittest.main()
