"""Kamui through the player command path and its temporary-room lifecycle."""

import tempfile
import unittest
from unittest.mock import patch

import combat
import data_mangekyo
import mangekyo
import world
from models import Account, Player
from session import Session, State


class KamuiCommandTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        rooms = {1: world.Room(1, "Starting room", "A room."),
                 2: world.Room(2, "Other room", "Another room.")}
        for target, value in (("session.ACTIVE_SESSIONS", []),
                              ("world.WORLD.rooms", rooms),
                              ("mangekyo._NEXT_POCKET_DIMENSION_VNUM", None),
                              ("storage.DATA_DIR", directory.name),
                              ("storage.ACCOUNTS_DIR", directory.name + "/accounts"),
                              ("storage.PLAYERS_DIR", directory.name + "/players")):
            item = patch(target, value)
            item.start()
            self.addCleanup(item.stop)
        self.caster, self.output = self.make_session("Caster", 1, eye=True)
        self.target, self.target_output = self.make_session("Target", 1)

    @staticmethod
    def make_session(name, room, eye=False):
        output = []
        session = Session(output.append, lambda: None)
        session.player = Player(name, name, room_vnum=room, chakra=500, maximum_chakra=500)
        session.player.village = "leaf"
        session.player.bloodline_id = "sharingan" if eye else None
        session.player.bloodline_mangekyo = eye
        session.player.mangekyo_eye_1 = "kamui" if eye else None
        session.player.sharingan_active = eye
        session.account = Account(name, "", "")
        session.state = State.PLAYING
        session.color_enabled = False
        output.clear()
        return session, output

    def test_all_three_casts_accept_displayed_name(self):
        self.caster.handle_line("perform kamui: intangibility")
        self.assertEqual(self.caster.player.kamui_intangibility_rounds_left, 3)
        self.caster.handle_line("perform kamui: limb removal Target")
        self.assertEqual(self.caster.pending_cast.jutsu_key, "kamui limb removal")
        self.assertIs(self.caster.pending_cast.target, self.target)
        self.caster.handle_line("perform kamui: pocket dimension Target")
        self.assertEqual(self.target.player.room_vnum,
                         self.caster.player.kamui_pocket_dimension_vnum)
        self.assertEqual(self.caster.player.room_vnum, 1)

    def test_short_cast_self_entry_and_chakra_collapse_restore_both(self):
        self.caster.handle_line("perform kamui Target")
        room = self.target.player.room_vnum
        self.caster.handle_line("perform kamui self")
        self.assertEqual(self.caster.player.room_vnum, room)
        self.caster.player.chakra = 0
        import session
        mangekyo.process_kamui_pocket_dimensions(combat, world, session)
        self.assertEqual((self.caster.player.room_vnum, self.target.player.room_vnum), (1, 1))
        self.assertNotIn(room, world.WORLD.rooms)
        self.assertIsNone(self.caster.player.kamui_pocket_dimension_vnum)

    def test_self_cast_creates_solo_dimension_with_upkeep_and_safe_return(self):
        self.caster.handle_line("perform kamui self")
        room = self.caster.player.room_vnum
        self.assertNotEqual(room, 1)
        self.assertEqual(room, self.caster.player.kamui_pocket_dimension_vnum)
        self.assertTrue(self.caster.player.kamui_pocket_dimension_active)
        self.assertEqual(self.caster.player.kamui_return_room_vnum, 1)
        self.assertIn("kamui", self.caster.player.mangekyo_eyes_used)
        self.assertEqual(self.target.player.room_vnum, 1)
        self.caster.handle_line("perform kamui self")
        self.assertIn("already inside", "".join(self.output))
        self.assertEqual(sum(r.name == "A Pocket Dimension" for r in world.WORLD.rooms.values()), 1)
        import session
        before = self.caster.player.chakra
        mangekyo.process_kamui_pocket_dimensions(combat, world, session)
        self.assertEqual(before - self.caster.player.chakra,
                         data_mangekyo.KAMUI_UPKEEP_ALONE_PER_TICK)
        self.caster.player.chakra = 0
        mangekyo.process_kamui_pocket_dimensions(combat, world, session)
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertNotIn(room, world.WORLD.rooms)

    def test_mob_can_be_sent_to_pocket_and_returns_on_collapse(self):
        mob = combat.Mob(9001, 9001, "bandit", 10, 100, 100, 1, 0, 0)
        with patch.dict(combat.MOBS_BY_ROOM, {1: [mob]}, clear=True):
            self.caster.handle_line("perform kamui bandit")
            room = self.caster.player.kamui_pocket_dimension_vnum
            self.assertEqual(mob.room_vnum, room)
            self.caster.handle_line("perform kamui self")
            self.assertEqual(self.caster.player.room_vnum, room)
            self.caster.player.chakra = 0
            import session
            mangekyo.process_kamui_pocket_dimensions(combat, world, session)
            self.assertEqual(mob.room_vnum, 1)
            self.assertIn(mob, combat.MOBS_BY_ROOM[1])

    def test_amaterasu_burn_on_mob_can_be_extinguished(self):
        mob = combat.Mob(9002, 9002, "bandit", 10, 100, 100, 1, 0, 0)
        self.caster.player.mangekyo_eye_1 = "amaterasu"
        with patch.dict(combat.MOBS_BY_ROOM, {1: [mob]}, clear=True):
            self.caster.handle_line("perform amaterasu bandit")
            self.assertIsNotNone(self.caster.pending_cast)
            import mangekyo_mobs
            mangekyo_mobs.resolve(self.caster, "amaterasu", mob)
            self.assertEqual(mob.mangekyo_amaterasu_caster, "Caster")
            self.caster.handle_line("perform amaterasu extinguish bandit")
            self.assertIsNone(mob.mangekyo_amaterasu_caster)

    def test_solo_pocket_disconnect_returns_caster(self):
        self.caster.handle_line("perform kamui: pocket dimension Caster")
        room = self.caster.player.room_vnum
        self.caster.request_close()
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertNotIn(room, world.WORLD.rooms)

    def test_no_second_dimension_or_transfer_from_another_pocket(self):
        self.caster.handle_line("perform kamui Target")
        room = self.target.player.room_vnum
        self.caster.handle_line("perform kamui Target")
        self.assertEqual(self.target.player.room_vnum, room)
        self.assertIn("nobody here", "".join(self.output))
        with self.assertRaises(ValueError):
            mangekyo.open_pocket_dimension(self.caster, self.target, world)
        other, other_output = self.make_session("Other", 2, eye=True)
        other.handle_line("perform kamui Target")
        self.assertEqual(self.target.player.room_vnum, room)
        self.assertIsNone(other.player.kamui_pocket_dimension_vnum)
        self.assertIn("nobody here", "".join(other_output))
        other.player.room_vnum = room
        with self.assertRaisesRegex(ValueError, "already inside a pocket dimension"):
            mangekyo.open_pocket_dimension(other, self.target, world)
        self.assertEqual(sum(r.name == "A Pocket Dimension" for r in world.WORLD.rooms.values()), 1)

    def test_disconnect_returns_target_before_save(self):
        self.caster.handle_line("perform kamui Target")
        room = self.target.player.room_vnum
        self.caster.request_close()
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertNotIn(room, world.WORLD.rooms)

    def test_target_disconnect_closes_unentered_dimension(self):
        self.caster.handle_line("perform kamui Target")
        room = self.target.player.room_vnum
        self.target.request_close()
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertIsNone(self.caster.player.kamui_pocket_dimension_vnum)
        self.assertNotIn(room, world.WORLD.rooms)

    def test_targeted_mangekyo_requires_same_room_before_spending_resources(self):
        self.target.player.room_vnum = 2
        for eye, command in (("tsukuyomi", "perform tsukuyomi Target"),
                             ("amaterasu", "perform amaterasu Target"),
                             ("kamui", "perform kamui Target"),
                             ("kamui", "perform kamui limb removal Target"),
                             ("izanami", "perform izanami Target")):
            with self.subTest(command=command):
                self.caster.player.mangekyo_eye_1 = eye
                self.output.clear()
                self.caster.handle_line(command)
                self.assertIn("nobody here", "".join(self.output))
                self.assertEqual(self.caster.player.chakra, 500)
                self.assertFalse(self.caster.player.cooldowns)
                self.assertIsNone(self.caster.pending_cast)
                self.assertIsNone(self.caster.player.kamui_pocket_dimension_vnum)
        with self.assertRaises(ValueError):
            mangekyo.open_pocket_dimension(self.caster, self.target, world)

    def test_delayed_mangekyo_fizzles_if_target_walks_away(self):
        for eye, command, resolver in (("tsukuyomi", "perform tsukuyomi Target", combat.resolve_tsukuyomi_cast),
                                       ("amaterasu", "perform amaterasu Target", combat.resolve_amaterasu_cast),
                                       ("kamui", "perform kamui limb removal Target", combat.resolve_kamui_limb_removal_cast),
                                       ("izanami", "perform izanami Target", combat.resolve_izanami_cast)):
            with self.subTest(command=command):
                self.caster.player.mangekyo_eye_1 = eye
                self.caster.handle_line(command)
                self.assertIsNotNone(self.caster.pending_cast)
                self.caster.pending_cast = None
                self.target.player.room_vnum = 2
                self.output.clear()
                resolver(self.caster, self.target)
                self.assertIn("no longer there", "".join(self.output))
                self.assertEqual(self.target.player.room_vnum, 2)
                self.assertFalse(self.target.player.mangekyo_amaterasu_burning)
                self.assertFalse(self.target.player.izanami_trapped)
                self.target.player.room_vnum = 1

    def test_amaterasu_burn_ends_on_defeat_and_room_fire_expires_in_five_minutes(self):
        self.caster.player.mangekyo_eye_1 = "amaterasu"
        with patch("storage.save_player"):
            combat.resolve_amaterasu_cast(self.caster, self.target)
        room = world.WORLD.get(1)
        self.assertTrue(self.target.player.mangekyo_amaterasu_burning)
        self.assertEqual(data_mangekyo.AMATERASU_ROOM_FIRE_DURATION_SECONDS, 5 * 60)
        import time
        self.assertAlmostEqual(room.amaterasu_fire_expires_at - time.time(), 5 * 60, delta=2)
        self.target.player.health = 0
        combat.handle_player_defeat(self.target)
        self.assertFalse(self.target.player.mangekyo_amaterasu_burning)
        self.assertTrue(room.amaterasu_fire_caster)
        with patch("mangekyo.time.time", return_value=room.amaterasu_fire_expires_at + 1):
            mangekyo.process_amaterasu_room_fires(combat, world)
        self.assertIsNone(room.amaterasu_fire_caster)


if __name__ == "__main__":
    unittest.main()
