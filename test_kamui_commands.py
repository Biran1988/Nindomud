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

    def test_amaterasu_mob_takes_immediate_damage_and_continues_burning(self):
        import mangekyo_mobs
        mob = combat.Mob(9003, 9003, "bandit", 10, 600, 600, 1, 0, 0)
        with patch.dict(combat.MOBS_BY_ROOM, {1: [mob]}, clear=True):
            mangekyo_mobs.resolve(self.caster, "amaterasu", mob)
            self.assertEqual(mob.health, 350)
            self.assertEqual(mob.mangekyo_amaterasu_caster, "Caster")
            self.assertIn("damage on impact", "".join(self.output))
            # The directly ignited mob continues burning even after moving
            # out of the room whose separate five-minute fire remains.
            combat.MOBS_BY_ROOM[1].remove(mob)
            combat.MOBS_BY_ROOM[2] = [mob]
            mob.room_vnum = 2
            with patch("combat.random.randint", return_value=45):
                combat.tick_all_mob_effects([self.caster])
            self.assertEqual(mob.health, 305)

    def test_amaterasu_immediate_mob_defeat_uses_normal_kill_handler(self):
        import mangekyo_mobs
        mob = combat.Mob(9004, 9004, "bandit", 10, 30, 30, 1, 0, 0)
        with patch.dict(combat.MOBS_BY_ROOM, {1: [mob]}, clear=True):
            with patch.object(combat, "handle_mob_defeat") as defeat:
                mangekyo_mobs.resolve(self.caster, "amaterasu", mob)
            self.assertEqual(mob.health, 0)
            defeat.assert_called_once_with(self.caster, mob)

    def test_amaterasu_burn_on_mob_cannot_be_extinguished(self):
        mob = combat.Mob(9002, 9002, "bandit", 10, 500, 500, 1, 0, 0)
        self.caster.player.mangekyo_eye_1 = "amaterasu"
        with patch.dict(combat.MOBS_BY_ROOM, {1: [mob]}, clear=True):
            self.caster.handle_line("perform amaterasu bandit")
            self.assertIsNotNone(self.caster.pending_cast)
            import mangekyo_mobs
            mangekyo_mobs.resolve(self.caster, "amaterasu", mob)
            self.assertEqual(mob.mangekyo_amaterasu_caster, "Caster")
            self.caster.handle_line("perform amaterasu extinguish bandit")
            self.assertEqual(mob.mangekyo_amaterasu_caster, "Caster")
            self.assertIn("they cannot be manually extinguished", "".join(self.output))
            # The caster can still dismiss the separately timed room fire.
            self.caster.handle_line("perform amaterasu extinguish all")
            self.assertIsNone(world.WORLD.get(1).amaterasu_fire_caster)
            self.assertEqual(mob.mangekyo_amaterasu_caster, "Caster")

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

    def test_amaterasu_player_takes_250_immediately_and_flames_end_on_defeat(self):
        self.caster.player.mangekyo_eye_1 = "amaterasu"
        self.target.player.maximum_health = 800
        self.target.player.health = 800
        with patch("storage.save_player"):
            combat.resolve_amaterasu_cast(self.caster, self.target)
            room = world.WORLD.get(1)
            self.assertEqual(self.target.player.health, 550)
            self.assertTrue(self.target.player.mangekyo_amaterasu_burning)
            self.assertEqual(self.target.player.mangekyo_amaterasu_caster, "Caster")
            self.assertEqual(data_mangekyo.AMATERASU_ROOM_FIRE_DURATION_SECONDS, 5 * 60)
            import time
            self.assertAlmostEqual(room.amaterasu_fire_expires_at - time.time(), 5 * 60, delta=2)
            self.target.player.health = 0
            combat.handle_player_defeat(self.target)
            self.assertFalse(self.target.player.mangekyo_amaterasu_burning)
            self.assertIsNone(self.target.player.mangekyo_amaterasu_caster)
            before = self.target.player.health
            import session as session_module
            with patch("random.randint", return_value=50):
                mangekyo.process_amaterasu_player_burns(combat, session_module)
            self.assertEqual(self.target.player.health, before)
        self.assertTrue(room.amaterasu_fire_caster)
        with patch("mangekyo.time.time", return_value=room.amaterasu_fire_expires_at + 1):
            mangekyo.process_amaterasu_room_fires(combat, world)
        self.assertIsNone(room.amaterasu_fire_caster)
        self.assertFalse(self.target.player.mangekyo_amaterasu_burning)

    def test_amaterasu_immortal_has_no_attached_flames_or_room_damage(self):
        import session as session_module
        self.target.account.staff_level = "immortal"
        self.target.player.maximum_health = 900
        self.target.player.health = 900
        with patch("storage.save_player"):
            combat.resolve_amaterasu_cast(self.caster, self.target)
            self.assertFalse(self.target.player.mangekyo_amaterasu_burning)
            self.assertIsNone(self.target.player.mangekyo_amaterasu_caster)
            self.assertEqual(self.target.player.mangekyo_amaterasu_expires_at, 0)
            before = self.target.player.health
            with patch.object(session_module, "ACTIVE_SESSIONS", [self.caster, self.target]):
                mangekyo.process_amaterasu_player_burns(combat, session_module)
                mangekyo.process_amaterasu_room_fires(combat, world)
            self.assertEqual(self.target.player.health, before)
            # Older saved immortals must also be unburned at the next pulse.
            self.target.player.mangekyo_amaterasu_burning = True
            self.target.player.mangekyo_amaterasu_expires_at = 0
            with patch.object(session_module, "ACTIVE_SESSIONS", [self.caster, self.target]):
                mangekyo.process_amaterasu_player_burns(combat, session_module)
            self.assertFalse(self.target.player.mangekyo_amaterasu_burning)

    def test_amaterasu_player_burn_expires_after_five_real_minutes(self):
        import session as session_module
        self.target.player.maximum_health = 1500
        self.target.player.health = 1500
        with patch("storage.save_player"):
            combat.resolve_amaterasu_cast(self.caster, self.target)
            expires = self.target.player.mangekyo_amaterasu_expires_at
            self.assertAlmostEqual(expires - __import__("time").time(), 300, delta=3)
            with patch.object(session_module, "ACTIVE_SESSIONS", [self.caster, self.target]):
                with patch("mangekyo.time.time", return_value=expires - 1), patch("mangekyo.random.randint", return_value=40):
                    mangekyo.process_amaterasu_player_burns(combat, session_module)
                self.assertTrue(self.target.player.mangekyo_amaterasu_burning)
                with patch("mangekyo.time.time", return_value=expires + 1):
                    mangekyo.process_amaterasu_player_burns(combat, session_module)
            self.assertFalse(self.target.player.mangekyo_amaterasu_burning)
            self.assertEqual(self.target.player.mangekyo_amaterasu_expires_at, 0)
            self.assertIsNone(self.target.player.mangekyo_amaterasu_caster)

    def test_amaterasu_mob_flaming_stops_after_death(self):
        import mangekyo_mobs
        mob = combat.Mob(9005, 9005, "bandit", 10, 600, 600, 1, 0, 0)
        with patch.dict(combat.MOBS_BY_ROOM, {1: [mob]}, clear=True):
            mangekyo_mobs.resolve(self.caster, "amaterasu", mob)
            self.assertEqual(mob.mangekyo_amaterasu_caster, "Caster")
            mob.health = 0
            with patch.object(combat, "handle_mob_defeat", wraps=combat.handle_mob_defeat):
                combat.handle_mob_defeat(self.caster, mob)
            self.assertIsNone(mob.mangekyo_amaterasu_caster)
            health = mob.health
            with patch("combat.random.randint", return_value=50):
                combat.tick_all_mob_effects([self.caster])
            self.assertEqual(mob.health, health)

    def test_amaterasu_initial_pvp_hit_uses_defenses(self):
        self.target.player.maximum_health = 800
        self.target.player.health = 800
        with patch("storage.save_player"), patch(
                "combat.status_effects.reduce_incoming_damage", return_value=125) as reducer:
            combat.resolve_amaterasu_cast(self.caster, self.target, grow_handsigns=False)
        reducer.assert_called_with(self.target.player.active_status_effects, 250)
        self.assertEqual(self.target.player.health, 675)
        self.assertTrue(self.target.player.mangekyo_amaterasu_burning)

    def test_amaterasu_initial_pvp_kill_uses_pvp_defeat(self):
        self.target.player.health = 100
        with patch("storage.save_player"), patch.object(combat, "handle_pvp_defeat") as defeat:
            combat.resolve_amaterasu_cast(self.caster, self.target, grow_handsigns=False)
        defeat.assert_called_once_with(winner_session=self.caster, loser_session=self.target)
        self.assertTrue(self.target.player.mangekyo_amaterasu_burning)


if __name__ == "__main__":
    unittest.main()
