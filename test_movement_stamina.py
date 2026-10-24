"""Movement costs stamina only when a room transition succeeds."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import commands
import general_skills
import world
from models import Player


class MovementStaminaTests(unittest.TestCase):
    def test_walking_charges_one_or_two_and_never_goes_negative(self):
        start = world.Room(701, "Start", "Start")
        finish = world.Room(702, "Finish", "Finish")
        start.exits["north"] = 702
        finish.exits["south"] = 701
        player = Player("Walker", "Walker")
        player.room_vnum = 701
        player.stamina = 3
        session = SimpleNamespace(player=player, account=None, combat_target=None,
                                  trade=None, send=Mock(), broadcast_room=Mock())
        with patch.object(commands.WORLD, "get", side_effect={701: start, 702: finish}.get), \
             patch.object(commands.combat, "mobs_in_room", return_value=[]), \
             patch.object(commands, "cmd_look"), \
             patch.object(commands, "_fire_enter_triggers"), \
             patch.object(commands.random, "randint", side_effect=[1, 2, 2]):
            commands.cmd_move(session, "west")
            self.assertEqual((player.room_vnum, player.stamina), (701, 3))
            start.exit_flags["north"] = ["door"]
            commands.cmd_move(session, "north")
            self.assertEqual((player.room_vnum, player.stamina), (701, 3))
            start.exit_door_open["north"] = True
            commands.cmd_move(session, "north")
            self.assertEqual((player.room_vnum, player.stamina), (702, 2))
            commands.cmd_move(session, "south")
            self.assertEqual((player.room_vnum, player.stamina), (701, 0))
            commands.cmd_move(session, "north")
            self.assertEqual((player.room_vnum, player.stamina), (701, 0))
            self.assertIn("too exhausted", session.send.call_args.args[0])

    def test_zero_stamina_prevents_walking_without_side_effects(self):
        start = world.Room(703, "Start", "Start")
        finish = world.Room(704, "Finish", "Finish")
        start.exits["north"] = finish.vnum
        player = Player("TiredWalker", "TiredWalker")
        player.room_vnum = start.vnum
        player.stamina = 0
        player.position = "resting"
        session = SimpleNamespace(player=player, account=None, combat_target=None,
                                  trade=None, send=Mock(), broadcast_room=Mock())
        with patch.object(commands.WORLD, "get", side_effect={703: start, 704: finish}.get), \
             patch.object(commands, "cmd_look") as look, \
             patch.object(commands, "_fire_enter_triggers") as enter, \
             patch.object(general_skills, "before_move") as before_move, \
             patch.object(commands.random, "randint") as roll:
            commands.cmd_move(session, "north")
            self.assertEqual(player.room_vnum, start.vnum)
            self.assertEqual(player.stamina, 0)
            self.assertEqual(player.position, "resting")
            self.assertIn("too exhausted", session.send.call_args.args[0])
            roll.assert_not_called()
            before_move.assert_not_called()
            look.assert_not_called()
            enter.assert_not_called()
            session.broadcast_room.assert_not_called()

    def test_one_stamina_cannot_pay_two_stamina_step(self):
        start = world.Room(705, "Start", "Start")
        finish = world.Room(706, "Finish", "Finish")
        start.exits["east"] = finish.vnum
        player = Player("LowWalker", "LowWalker")
        player.room_vnum = start.vnum
        player.stamina = 1
        session = SimpleNamespace(player=player, account=None, combat_target=None,
                                  trade=None, send=Mock(), broadcast_room=Mock())
        with patch.object(commands.WORLD, "get", side_effect={705: start, 706: finish}.get), \
             patch.object(commands.combat, "mobs_in_room", return_value=[]), \
             patch.object(commands, "cmd_look") as look, \
             patch.object(commands, "_fire_enter_triggers") as enter, \
             patch.object(general_skills, "before_move") as before_move, \
             patch.object(commands.random, "randint", return_value=2):
            commands.cmd_move(session, "east")
            self.assertEqual((player.room_vnum, player.stamina), (705, 1))
            self.assertIn("need 2 stamina", session.send.call_args.args[0])
            before_move.assert_not_called()
            session.broadcast_room.assert_not_called()
            enter.assert_not_called()
            look.assert_not_called()

    def test_last_stamina_can_be_spent_and_recovery_allows_walking_again(self):
        start = world.Room(707, "Start", "Start")
        finish = world.Room(708, "Finish", "Finish")
        start.exits["north"] = finish.vnum
        finish.exits["south"] = start.vnum
        player = Player("RecoveringWalker", "RecoveringWalker")
        player.room_vnum = start.vnum
        player.stamina = 1
        session = SimpleNamespace(player=player, account=None, combat_target=None,
                                  trade=None, send=Mock(), broadcast_room=Mock())
        with patch.object(commands.WORLD, "get", side_effect={707: start, 708: finish}.get), \
             patch.object(commands.combat, "mobs_in_room", return_value=[]), \
             patch.object(commands, "cmd_look"), \
             patch.object(commands, "_fire_enter_triggers"), \
             patch.object(commands.random, "randint", side_effect=[1, 2]):
            commands.cmd_move(session, "north")
            self.assertEqual((player.room_vnum, player.stamina), (708, 0))
            commands.cmd_move(session, "south")
            self.assertEqual((player.room_vnum, player.stamina), (708, 0))
            player.stamina = 2  # Resting or natural regeneration replenished it.
            commands.cmd_move(session, "south")
            self.assertEqual((player.room_vnum, player.stamina), (707, 0))


if __name__ == "__main__":
    unittest.main()
