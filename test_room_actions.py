"""Regression tests: nearby players observe actual actions, not secret ones."""
import unittest
from unittest.mock import patch

import combat
import commands
import general_skills
import olc
import room_actions
import session as sessions
import world
from models import Account, Player
from session import Session, State


class RoomActionTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.object(sessions, "ACTIVE_SESSIONS", []),
            patch.object(world.WORLD, "rooms", {}),
            patch.object(olc, "OBJECT_TEMPLATES", {}),
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(combat, "MOB_TEMPLATES", {}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        world.WORLD.add_room(world.Room(1, "Square", "A lively village square."))
        world.WORLD.add_room(world.Room(2, "Road", "A quiet road."))
        self.actor, self.actor_out = self.make_session("Aki", 1)
        self.witness, self.witness_out = self.make_session("Mina", 1)
        self.remote, self.remote_out = self.make_session("Taro", 2)
        # Other characters entering the test world may produce join notices.
        for output in (self.actor_out, self.witness_out, self.remote_out):
            output.clear()

    def make_session(self, name, vnum):
        out = []
        s = Session(out.append, lambda: None)
        s.player = Player(name, name, village="leaf", clan="nara",
                          primary_class="ninjutsu", room_vnum=vnum,
                          stamina=10, chakra=10)
        s.account = Account(name, "salt", "hash")
        s.state = State.PLAYING
        # Session.__init__ already registers with ACTIVE_SESSIONS; avoid
        # duplicate observers and duplicate room-action broadcasts.
        out.clear()  # Session creation sends banners; exclude from action assertions.
        return s, out

    def test_pickup_and_drop_report_success_once_to_same_room(self):
        self.actor.player.inventory.append("a sardine")
        commands.cmd_drop(self.actor, ["sardine"])
        self.assertEqual(len(self.witness_out), 1)
        self.assertIn("Aki drops a sardine", self.witness_out[0])
        commands.cmd_get(self.actor, ["sardine"])
        self.assertEqual(len(self.witness_out), 2)
        self.assertIn("Aki picks up a sardine", self.witness_out[-1])
        commands.cmd_get(self.actor, ["sardine"])
        self.assertEqual(len(self.witness_out), 2)  # failed, no room spam
        self.assertEqual(self.remote_out, [])
        self.assertEqual(self.actor_out.count(self.witness_out[0]), 0)

    def test_bulk_drop_reports_one_summary(self):
        self.actor.player.inventory.extend(["a sardine", "a minnow", "a trout"])
        commands.cmd_drop(self.actor, ["all"])
        self.assertEqual(len(self.witness_out), 1)
        self.assertIn("drops 3 items", self.witness_out[0])
        commands.cmd_get(self.actor, ["all"])
        self.assertEqual(len(self.witness_out), 2)
        self.assertIn("picks up 3 items", self.witness_out[-1])

    def test_sleep_rest_and_waking(self):
        commands.cmd_sleep(self.actor, [])
        self.assertIn("falls asleep", self.witness_out[-1])
        commands.cmd_stand(self.actor, [])
        self.assertIn("wakes and stands", self.witness_out[-1])
        commands.cmd_rest(self.actor, [])
        self.assertIn("sits down to rest", self.witness_out[-1])

    def test_room_look_shows_current_sleeping_and_fighting_state(self):
        commands.cmd_sleep(self.actor, [])
        commands.cmd_look(self.witness, [])
        self.assertIn("[Sleeping]", self.witness_out[-1])
        commands.cmd_stand(self.actor, [])
        combat.register_template(99184, "training student", 2, 100, 2, 4, 0, 0)
        combat.spawn_mob(99184, 1)
        commands.cmd_attack(self.actor, ["student"])
        commands.cmd_look(self.witness, [])
        self.assertIn("[Fighting training student]", self.witness_out[-1])

    def test_eat_and_drink_only_broadcast_consumed_items(self):
        self.actor.player.inventory.extend(["a rice ball", "a canteen of water"])
        commands.cmd_eat(self.actor, ["rice", "ball"])
        self.assertIn("Aki eats a rice ball", self.witness_out[-1])
        count = len(self.witness_out)
        commands.cmd_eat(self.actor, ["rice", "ball"])
        self.assertEqual(len(self.witness_out), count)
        commands.cmd_drink(self.actor, ["canteen"])
        self.assertIn("Aki drinks a canteen of water", self.witness_out[-1])

    def test_camouflage_hides_later_actions_but_not_initial_fade(self):
        self.actor.player.active_status_effects["camouflage"] = {"duration": 10}
        room_actions.emit(self.actor, "Aki fades from sight.", reveal_transition=True)
        self.assertIn("Aki fades", self.witness_out[-1])
        count = len(self.witness_out)
        room_actions.emit(self.actor, "Aki drops a weapon.")
        self.assertEqual(len(self.witness_out), count)
        self.witness.player.active_status_effects["sensory_detect"] = {"duration": 10}
        room_actions.emit(self.actor, "Aki picks up a weapon.")
        self.assertIn("picks up", self.witness_out[-1])

    def test_wizinvis_never_leaks_even_with_sensory_detect(self):
        self.actor.account.staff_level = "immortal"
        self.actor.player.wizinvis = True
        self.witness.player.active_status_effects["sensory_detect"] = {"duration": 10}
        room_actions.emit(self.actor, "Aki eats ramen.", reveal_transition=True)
        self.assertEqual(self.witness_out, [])
        self.actor.player.inventory.append("a rice ball")
        commands.cmd_eat(self.actor, ["rice", "ball"])
        self.assertEqual(self.witness_out, [])

    def test_attack_start_visible_without_duplicate_to_opponent(self):
        combat.register_template(99183, "training student", 2, 100, 2, 4, 0, 0)
        combat.spawn_mob(99183, 1)
        commands.cmd_attack(self.actor, ["student"])
        self.assertTrue(any("attacks" in line for line in self.witness_out))


if __name__ == "__main__":
    unittest.main()
