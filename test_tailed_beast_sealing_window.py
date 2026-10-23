"""A downed beast must survive normal server pulses until sealed or expired."""
import time
import unittest
from unittest.mock import patch

import combat
import commands
import data_tailed_beasts
import mangekyo
import skill_training
import tailed_beasts
import world
from models import Account, Player
from session import ACTIVE_SESSIONS, Session, State
import session as session_module


class TailedBeastSealingWindowTests(unittest.TestCase):
    def setUp(self):
        self.room = world.Room(992850, "Sealing Clearing", "An empty clearing.")
        world.WORLD.rooms[self.room.vnum] = self.room
        self.addCleanup(world.WORLD.rooms.pop, self.room.vnum, None)
        combat.MOBS_BY_ROOM[self.room.vnum] = []
        self.addCleanup(combat.MOBS_BY_ROOM.pop, self.room.vnum, None)
        self.output = []
        self.s = Session(self.output.append, lambda: None)
        self.s.player = Player("Sealer", "Sealer", level=100, room_vnum=self.room.vnum)
        self.s.account = Account("Sealer", "salt", "hash")
        self.s.state = State.PLAYING
        self.addCleanup(ACTIVE_SESSIONS.remove, self.s)
        self.s.player.learned_skills.append("Sealing Jutsu")
        self.s.player.practice_gate_enabled = True
        skill_training.grant_without_practice(self.s.player, "Sealing Jutsu")
        self.s.player.chakra = 1000
        self.output.clear()

    def down_beast(self, beast):
        mob = combat.Mob(95000 + beast["tails"] - 1, 95000 + beast["tails"] - 1,
                         beast["display_name"], 100, beast["max_health"], 0,
                         self.room.vnum, 0, 0)
        mob.tailed_beast_key = beast["key"]
        mob.tailed_beast_despawn_at = time.time() + 7200
        combat.MOBS_BY_ROOM[self.room.vnum].append(mob)
        self.s.combat_target = mob
        combat.handle_mob_defeat(self.s, mob)
        return mob

    def test_all_nine_remain_targetable_after_effects_pulses_then_seal(self):
        for beast in data_tailed_beasts.TAILED_BEASTS:
            with self.subTest(beast=beast["key"]):
                mob = self.down_beast(beast)
                deadline = mob.tailed_beast_downed_until
                for _ in range(3):
                    combat.tick_all_mob_effects([self.s])
                    tailed_beasts.process_tailed_beasts(combat, world, session_module)
                self.assertIs(combat.find_mob(self.room.vnum, mob.name), mob)
                self.assertEqual(mob.tailed_beast_downed_until, deadline)
                self.s.player.chakra = 1000
                self.s.player.jinchuriki_beast_key = None
                commands.dispatch_line(self.s, "perform sealing jutsu " + mob.name)
                self.assertEqual(self.s.player.jinchuriki_beast_key, beast["key"])
                self.assertNotIn(mob, combat.mobs_in_room(self.room.vnum))
                self.assertEqual(self.s.player.chakra, 900)

    def test_repeated_defeat_and_damage_do_not_kill_or_extend_window(self):
        mob = self.down_beast(data_tailed_beasts.TAILED_BEASTS[0])
        deadline = mob.tailed_beast_downed_until
        mob.health = -50
        combat.handle_mob_defeat(self.s, mob)
        self.assertEqual(mob.health, 0)
        self.assertEqual(mob.tailed_beast_downed_until, deadline)
        self.assertEqual(self.s.player.npc_kills, 0)
        mob.mangekyo_amaterasu_caster = "Sealer"
        mob.active_status_effects["poisoned"] = {"duration": 3, "source": "Sealer"}
        self.room.amaterasu_fire_caster = "Sealer"
        self.room.amaterasu_fire_expires_at = time.time() + 300
        # Also exercise the no-owner branch that would otherwise delete a mob.
        with patch.object(session_module, "ACTIVE_SESSIONS", []):
            for _ in range(3):
                combat.tick_all_mob_effects([])
                mangekyo.process_amaterasu_room_fires(combat, world)
        self.assertIn(mob, combat.mobs_in_room(self.room.vnum))
        self.assertEqual(mob.tailed_beast_downed_until, deadline)
        self.assertEqual(mob.health, 0)

    def test_expiry_still_removes_beast_at_original_deadline(self):
        mob = self.down_beast(data_tailed_beasts.TAILED_BEASTS[0])
        with patch.object(tailed_beasts.time, "time", return_value=mob.tailed_beast_downed_until):
            tailed_beasts.process_tailed_beasts(combat, world, session_module)
        self.assertNotIn(mob, combat.mobs_in_room(self.room.vnum))
        before = self.s.player.chakra
        commands.dispatch_line(self.s, "perform sealing jutsu shukaku")
        self.assertIsNone(self.s.player.jinchuriki_beast_key)
        self.assertEqual(self.s.player.chakra, before)


if __name__ == "__main__":
    unittest.main()
