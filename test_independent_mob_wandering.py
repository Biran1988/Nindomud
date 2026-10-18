"""Wander movements belong to individual live mobs, not area-reset cohorts."""
import unittest
from unittest.mock import patch

import combat
import world


class IndependentMobWanderTests(unittest.TestCase):
    def setUp(self):
        for target, attribute in ((combat, "MOB_TEMPLATES"),
                                  (combat, "MOBS_BY_ROOM"),
                                  (world.WORLD, "rooms")):
            p = patch.object(target, attribute, {})
            p.start()
            self.addCleanup(p.stop)
        for vnum in (1101, 1102, 1103):
            world.WORLD.add_room(world.Room(vnum, f"Passage {vnum}", "Training corridor."))
        world.WORLD.rooms[1101].exits["east"] = 1102
        world.WORLD.rooms[1102].exits["west"] = 1101
        world.WORLD.rooms[1102].exits["east"] = 1103
        world.WORLD.rooms[1103].exits["west"] = 1102
        combat.register_template(91001, "a ninja student", 3, 30, 2, 5, 10, 5)
        combat.MOB_TEMPLATES[91001]["act_flags"] = ["Npc", "Wander"]
        self.now = 1000.0
        p = patch.object(combat.time, "time", side_effect=lambda: self.now)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(combat, "_broadcast_to_room")
        self.broadcast = p.start()
        self.addCleanup(p.stop)
        p = patch.object(combat, "_mob_is_being_fought", return_value=False)
        self.fighting = p.start()
        self.addCleanup(p.stop)

    def test_cohort_spawn_has_distinct_first_wander_deadlines(self):
        mobs = [combat.spawn_mob(91001, 1101) for _ in range(16)]
        deadlines = sorted(m.next_wander_at for m in mobs)
        self.assertEqual(len({m.instance_id for m in mobs}), 16)
        self.assertTrue(all(m.next_wander_at > self.now for m in mobs))
        self.assertTrue(all(b - a >= combat.WANDER_SPACING_SECONDS
                            for a, b in zip(deadlines, deadlines[1:])))
        self.assertEqual(len({id(m.wander_rng) for m in mobs}), 16)

    def test_simultaneously_due_mobs_do_not_leave_room_together(self):
        first, second, third = [combat.spawn_mob(91001, 1101) for _ in range(3)]
        first.next_wander_at = 1001.0
        second.next_wander_at = 1001.0  # simulate a pre-fix aligned timer
        third.next_wander_at = 1500.0
        self.now = 1002.0
        combat.process_wander()
        self.assertEqual(len(combat.MOBS_BY_ROOM[1101]), 2)
        self.assertEqual(len(combat.MOBS_BY_ROOM[1102]), 1)
        self.assertEqual(third.next_wander_at, 1500.0)
        departed = first if first.room_vnum == 1102 else second
        waiting = second if departed is first else first
        self.assertGreater(waiting.next_wander_at, self.now)
        self.assertNotEqual(waiting.next_wander_at, departed.next_wander_at)
        self.assertEqual(self.broadcast.call_count, 2)

    def test_moving_into_later_room_is_not_second_move_same_pulse(self):
        first = combat.spawn_mob(91001, 1101)
        first.next_wander_at = 1001.0
        self.now = 1002.0
        combat.process_wander()
        self.assertEqual(first.room_vnum, 1102)
        self.assertEqual(self.broadcast.call_count, 2)
        self.assertGreater(first.next_wander_at, self.now)

    def test_own_cooldown_remains_when_another_mob_cannot_move(self):
        first, second = [combat.spawn_mob(91001, 1101) for _ in range(2)]
        first.next_wander_at = 1001.0
        second.next_wander_at = 1600.0
        self.fighting.side_effect = lambda mob: mob is first
        self.now = 1002.0
        combat.process_wander()
        self.assertEqual(first.room_vnum, 1101)
        self.assertEqual(second.room_vnum, 1101)
        self.assertEqual(second.next_wander_at, 1600.0)
        self.assertGreater(first.next_wander_at, self.now)
        self.broadcast.assert_not_called()

    def test_no_wander_destination_is_excluded_without_blocking_exits(self):
        protected = world.WORLD.rooms[1102]
        protected.flags.append("no_wander")
        mob = combat.spawn_mob(91001, 1101)
        mob.next_wander_at = 1001.0
        self.now = 1002.0
        combat.process_wander()
        self.assertEqual(mob.room_vnum, 1101)
        self.broadcast.assert_not_called()
        self.assertGreater(mob.next_wander_at, self.now)

        protected.flags.remove("no_wander")
        mob.next_wander_at = 1001.0
        combat.process_wander()
        self.assertEqual(mob.room_vnum, 1102)

    def test_mob_can_wander_out_of_no_wander_room_if_spawned_there(self):
        world.WORLD.rooms[1102].flags.append("no_wander")
        mob = combat.spawn_mob(91001, 1102)
        mob.next_wander_at = 1001.0
        self.now = 1002.0
        combat.process_wander()
        self.assertIn(mob.room_vnum, (1101, 1103))

    def test_tailed_beast_roam_also_respects_no_wander(self):
        import tailed_beasts
        import session as session_module
        protected = world.WORLD.rooms[1102]
        protected.flags.append("no_wander")
        mob = combat.spawn_mob(91001, 1101)
        mob.tailed_beast_key = "one_tail"
        mob.tailed_beast_despawn_at = 100000.0
        mob.next_wander_at = 1001.0
        self.now = 1002.0
        with patch.object(tailed_beasts.time, "time", side_effect=lambda: self.now), \
             patch.object(session_module, "ACTIVE_SESSIONS", []):
            tailed_beasts.process_tailed_beasts(combat, world, session_module)
            self.assertEqual(mob.room_vnum, 1101)
            protected.flags.remove("no_wander")
            mob.next_wander_at = 1001.0
            tailed_beasts.process_tailed_beasts(combat, world, session_module)
            self.assertEqual(mob.room_vnum, 1102)

    def test_sentinel_never_gets_a_wander_clock(self):
        combat.MOB_TEMPLATES[91001]["act_flags"] = ["Npc", "Wander", "Sentinel"]
        mob = combat.spawn_mob(91001, 1101)
        self.assertEqual(mob.next_wander_at, 0.0)
        self.now = 1800.0
        combat.process_wander()
        self.assertEqual(mob.room_vnum, 1101)

    def test_mobs_with_same_template_have_independent_next_moves(self):
        first = combat.spawn_mob(91001, 1101)
        second = combat.spawn_mob(91001, 1102)
        first.next_wander_at = 1001.0
        second.next_wander_at = 1800.0
        self.now = 1002.0
        combat.process_wander()
        self.assertEqual(first.room_vnum, 1102)
        self.assertEqual(second.room_vnum, 1102)
        self.assertEqual(second.next_wander_at, 1800.0)
        self.assertNotEqual(first.next_wander_at, second.next_wander_at)


if __name__ == "__main__":
    unittest.main()
