"""Room-based Hidden Mist, targeting, and unchanged Ushiro opener rules."""

import time
import unittest
from unittest.mock import patch

import combat
import commands
import hidden_mist
import leveling
import world
from models import Player
from session import ACTIVE_SESSIONS, Session, State


class HiddenMistTests(unittest.TestCase):
    def setUp(self):
        self.room = world.Room(991170, "Mist Test", "A testing room.")
        world.WORLD.rooms[self.room.vnum] = self.room
        self.output, self.enemy_output = [], []
        self.caster = Session(self.output.append, lambda: None)
        self.enemy = Session(self.enemy_output.append, lambda: None)
        self.caster.state = self.enemy.state = State.PLAYING
        self.caster.player = Player("MistNinja", "MistNinja", primary_class="ninjutsu", level=75)
        self.caster.player.room_vnum = self.room.vnum
        self.caster.player.chakra_nature = "water"
        self.caster.player.chakra = 500
        self.enemy.player = Player("EnemyNinja", "EnemyNinja", primary_class="taijutsu", level=75)
        self.enemy.player.room_vnum = self.room.vnum
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(self.caster.player)

    def tearDown(self):
        ACTIVE_SESSIONS.remove(self.caster)
        ACTIVE_SESSIONS.remove(self.enemy)
        world.WORLD.rooms.pop(self.room.vnum, None)

    def cast_mist(self):
        commands.cmd_perform(self.caster, ["hidden", "mist", "jutsu"])
        self.assertIsNotNone(self.caster.pending_cast)
        self.caster.pending_cast.remaining_seconds = 0
        combat.tick_pending_casts()
        self.assertTrue(hidden_mist.room_active(self.room))

    def test_room_mist_hides_caster_and_expires(self):
        self.cast_mist()
        self.assertEqual(self.room.hidden_mist_caster, "MistNinja")
        self.assertEqual(hidden_mist.advantage(self.caster.player, self.enemy.player), 15)
        commands.cmd_attack(self.enemy, ["MistNinja"])
        self.assertIsNone(self.enemy.pvp_target)
        self.assertIn("cannot lock onto", "".join(self.enemy_output))
        self.enemy_output.clear()
        commands.cmd_look(self.enemy, [])
        self.assertIn("dense hidden mist", "".join(self.enemy_output))
        self.assertNotIn("MistNinja is here", "".join(self.enemy_output))

        # A person entering after the cast is also unable to target its caster.
        visitor = Player("Visitor", "Visitor", room_vnum=self.room.vnum)
        self.assertTrue(hidden_mist.obscures(visitor, self.caster.player))
        self.caster.player.room_vnum += 1
        self.assertFalse(hidden_mist.active(self.caster.player))
        self.caster.player.room_vnum = self.room.vnum
        self.room.hidden_mist_expires_at = time.time() - 1
        hidden_mist.process_rooms([self.caster, self.enemy])
        self.assertIsNone(self.room.hidden_mist_caster)
        self.assertEqual(hidden_mist.advantage(self.caster.player, self.enemy.player), 0)

    def test_ushiro_stays_an_opener(self):
        self.cast_mist()
        mob = combat.Mob(991171, 991171, "Training Mob", 30, 400, 400, 1, 0, 0)
        mob.room_vnum = self.room.vnum
        combat.MOBS_BY_ROOM[self.room.vnum] = [mob]
        try:
            self.caster.combat_target = mob
            commands.cmd_perform(self.caster, ["ushiro", "shishou", "training"])
            self.assertIn("mid-fight", "".join(self.output))
            self.caster.combat_target = None
            mob.health -= 1
            commands.cmd_perform(self.caster, ["ushiro", "shishou", "training"])
            self.assertIn("hurt and alert", "".join(self.output))
        finally:
            combat.MOBS_BY_ROOM.pop(self.room.vnum, None)

    def test_mist_turns_a_missed_attack_into_a_hit(self):
        self.cast_mist()
        mob = combat.Mob(991172, 991172, "Training Mob", 30, 400, 400, 1, 0, 0)
        mob.room_vnum = self.room.vnum
        with patch.object(combat.derived_stats, "to_hit_chance", return_value=50), \
             patch.object(combat.derived_stats, "critical_chance", return_value=0), \
             patch.object(combat.random, "randint", return_value=60), \
             patch.object(combat, "_player_attack_damage", return_value=10):
            combat._player_attack_mob_once(self.caster, self.caster.player, mob)
            self.assertLess(mob.health, 400)
            mob.health = 400
            self.room.hidden_mist_expires_at = time.time() - 1
            combat._player_attack_mob_once(self.caster, self.caster.player, mob)
            self.assertEqual(mob.health, 400)

    def test_requires_water_and_level(self):
        self.caster.player.chakra_nature = "fire"
        commands.cmd_perform(self.caster, ["hidden", "mist", "jutsu"])
        self.assertIsNone(self.caster.pending_cast)
        self.assertFalse(hidden_mist.room_active(self.room))

    def test_pending_targeted_cast_loses_target_when_mist_forms(self):
        self.enemy.player.learned_skills.append("Chakra Ball")
        combat.begin_pending_cast(self.enemy, "chakra ball", self.caster, is_pvp=True)
        self.enemy.pending_cast.remaining_seconds = 0
        self.cast_mist()
        # Both casts finish this pulse; the mist forms before the attack lands.
        self.assertIsNone(self.enemy.pending_cast)
        self.assertIn("mist swallows your target", "".join(self.enemy_output))


if __name__ == "__main__":
    unittest.main()
