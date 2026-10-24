"""Paid room mist and Chisei toggles, including cleanup and saved bonuses."""
import os
import tempfile
import unittest
from unittest.mock import patch

import combat
import commands
import genjutsu
import hidden_mist
import room_jutsu_objects
import session as sessions
import status_effects
import storage
import world
from models import Account, Player
from session import Session, State


class MaintainedToggleTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for item in (patch.object(world.WORLD, "rooms", {}),
                     patch.object(combat, "MOBS_BY_ROOM", {}),
                     patch.object(sessions, "ACTIVE_SESSIONS", []),
                     patch.object(storage, "DATA_DIR", folder.name),
                     patch.object(storage, "PLAYERS_DIR", os.path.join(folder.name, "players")),
                     patch.object(storage, "ACCOUNTS_DIR", os.path.join(folder.name, "accounts"))):
            item.start()
            self.addCleanup(item.stop)
        self.room = world.Room(1, "Clearing", "Open ground.")
        world.WORLD.add_room(self.room)
        world.WORLD.add_room(world.Room(2, "Path", "A nearby path."))
        self.out = []
        self.s = Session(self.out.append, lambda: None)
        self.s.player = Player("Maintainer", "Maintainer", level=75, village="leaf",
                               room_vnum=1, chakra=500, maximum_chakra=500,
                               primary_class="genjutsu", chakra_nature="water")
        self.s.player.learned_skills = ["Hidden Mist Jutsu", "Chisei", "Silent Genjutsu"]
        self.s.account = Account("Maintainer", "salt", "hash")
        self.s.state = State.PLAYING
        self.out.clear()

    def test_mist_stays_where_cast_and_charges_owner_only_once_per_interval(self):
        with patch.object(hidden_mist.time, "time", return_value=1000):
            self.assertTrue(hidden_mist.cast(self.s))
        self.s.player.room_vnum = 2
        self.assertTrue(hidden_mist.room_active(self.room))
        self.assertFalse(hidden_mist.active(self.s.player))
        before = self.s.player.chakra
        with patch.object(hidden_mist.time, "time", return_value=1005):
            hidden_mist.process_rooms([self.s])
            hidden_mist.process_rooms([self.s])
        self.assertEqual(self.s.player.chakra, before - 1)
        self.assertIsNotNone(room_jutsu_objects.find(self.room, "mist"))
        with patch.object(hidden_mist.time, "time", return_value=1009):
            hidden_mist.process_rooms([self.s])
        self.assertEqual(self.s.player.chakra, before - 1)
        self.s.player.chakra = 0
        with patch.object(hidden_mist.time, "time", return_value=1010):
            hidden_mist.process_rooms([self.s])
        self.assertFalse(hidden_mist.room_active(self.room))
        self.assertIsNone(room_jutsu_objects.find(self.room, "mist"))

    def test_mist_command_toggle_pending_cancel_and_remote_off(self):
        # Turning off can cancel hand signs before any activation cost.
        self.s.player.learned_skills.remove("Silent Genjutsu")
        commands.cmd_perform(self.s, ["hidden", "mist", "jutsu", "on"])
        self.assertIsNotNone(self.s.pending_cast)
        before = self.s.player.chakra
        commands.cmd_perform(self.s, ["hidden", "mist", "jutsu", "off"])
        self.assertIsNone(self.s.pending_cast)
        self.assertEqual(self.s.player.chakra, before)
        commands.cmd_perform(self.s, ["hidden", "mist", "jutsu", "on"])
        self.s.pending_cast.remaining_seconds = 0
        combat.tick_pending_casts()
        self.assertTrue(hidden_mist.room_active(self.room))
        before = self.s.player.chakra
        commands.cmd_perform(self.s, ["hidden", "mist", "jutsu", "on"])
        self.assertEqual(self.s.player.chakra, before)
        self.s.player.room_vnum = 2
        commands.cmd_perform(self.s, ["hidden", "mist", "jutsu"])
        self.assertFalse(hidden_mist.room_active(self.room))

    def test_mist_ends_if_owner_disconnects_or_is_absent(self):
        hidden_mist.cast(self.s)
        hidden_mist.process_rooms([])
        self.assertFalse(hidden_mist.room_active(self.room))
        self.s.player.cooldowns.clear()
        hidden_mist.cast(self.s)
        self.s.request_close()
        self.assertFalse(hidden_mist.room_active(self.room))

    def test_chisei_stays_on_pays_upkeep_and_never_stacks(self):
        with patch.object(genjutsu.time, "time", return_value=1000):
            genjutsu.begin_cast(self.s, "chisei", ["on"])
        maximum = self.s.player.maximum_chakra
        self.assertGreater(maximum, 500)
        with patch.object(genjutsu.time, "time", return_value=1005):
            before = self.s.player.chakra
            combat.tick_effects_pulse(self.s)
            combat.tick_effects_pulse(self.s)
            self.assertEqual(self.s.player.chakra, before - 1)
            genjutsu.begin_cast(self.s, "chisei", ["on"])
            self.assertEqual(self.s.player.maximum_chakra, maximum)
            for _ in range(100):
                status_effects.tick_effects(self.s.player.active_status_effects)
        self.assertIn("chisei", self.s.player.active_status_effects)
        commands.cmd_perform(self.s, ["chisei", "off"])
        self.assertEqual(self.s.player.maximum_chakra, 500)
        self.assertEqual(self.s.player.chisei_chakra_bonus, 0)
        genjutsu.clear_chisei(self.s.player)
        self.assertEqual(self.s.player.maximum_chakra, 500)

    def test_chisei_upkeep_failure_and_save_reload_remove_no_extra_capacity(self):
        genjutsu.begin_cast(self.s, "chisei", [])
        storage.save_player(self.s.player)
        loaded = storage.load_player(self.s.player.name)
        self.assertEqual(loaded.maximum_chakra, self.s.player.maximum_chakra)
        self.s.player = loaded
        loaded.chakra = 0
        with patch.object(genjutsu.time, "time", return_value=loaded.chisei_next_upkeep_at):
            combat.tick_effects_pulse(self.s)
        self.assertNotIn("chisei", loaded.active_status_effects)
        self.assertEqual(loaded.maximum_chakra, 500)
        self.assertEqual(loaded.chakra, 0)
        self.assertEqual(combat._genjutsu_hit_bonus(loaded, {"class_requirement": "genjutsu"}), 0)


if __name__ == "__main__":
    unittest.main()
