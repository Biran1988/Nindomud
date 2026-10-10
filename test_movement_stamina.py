"""Movement costs stamina only when a room transition succeeds."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import commands
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
            self.assertEqual((player.room_vnum, player.stamina), (702, 0))


if __name__ == "__main__":
    unittest.main()
