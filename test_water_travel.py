"""Ocean travel regression checks for ports, roomless map and boundary turns."""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import commands
import storage
import water_travel as ocean
import world
from models import Player


class BoatNavigationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p = patch.object(storage, "DATA_DIR", temp.name)
        p.start()
        self.addCleanup(p.stop)
        save = patch.object(storage, "save_player")
        save.start()
        self.addCleanup(save.stop)
        self.player = Player("WaterPilot", "WaterPilot", ryo=90000, room_vnum=918211)
        self.session = SimpleNamespace(player=self.player, send=Mock(),
                                       account=SimpleNamespace(staff_level="admin"),
                                       combat_target=None, pvp_target=None,
                                       state=SimpleNamespace(name="PLAYING"))
        self.room = world.Room(918211, "Test Harbor", "A shoreline")
        world.WORLD.add_room(self.room)
        self.addCleanup(lambda: world.WORLD.rooms.pop(918211, None))
        self.addCleanup(lambda: world.WORLD.rooms.pop(ocean.boat_room_vnum(self.player), None))

    def test_10000_ryo_purchase_and_insufficient_funds(self):
        ocean.command_setport(self.session, ["10", "10", "Budget", "Harbor"])
        self.assertEqual(ocean.BOAT_PRICE_RYO, 10_000)
        self.player.ryo = 9_999
        ocean.buy_boat(self.session)
        self.assertFalse(ocean.state(self.player).get("owned"))
        self.assertEqual(self.player.ryo, 9_999)
        self.assertTrue(any("10,000" in str(call)
                            for call in self.session.send.call_args_list))
        self.player.ryo = 10_000
        ocean.buy_boat(self.session)
        self.assertTrue(self.player.boat_state["owned"])
        self.assertEqual(self.player.ryo, 0)

    def test_ownership_room_course_and_bounds(self):
        ocean.command_setport(self.session, ["19980", "19980", "Test", "Harbor"])
        ocean.buy_boat(self.session)
        self.assertTrue(self.player.boat_state["owned"])
        self.assertEqual(self.player.ryo, 90000 - ocean.BOAT_PRICE_RYO)
        with patch.object(commands, "cmd_look"):
            ocean.command_board(self.session, ["boat"])
        self.assertTrue(ocean.is_aboard(self.player))
        room = world.WORLD.get(ocean.boat_room_vnum(self.player))
        self.assertEqual(room.name, "WaterPilot's Boat - Helm")
        self.assertFalse(room.exits)
        ocean.command_course(self.session, ["20000", "20000"])
        ocean.tick_boats([self.session], 2)
        self.assertEqual(self.player.boat_state["course"], [19500, 19500])
        ocean.tick_boats([self.session], 1)
        self.assertLess(self.player.boat_state["x"], 20000)
        ocean.command_course(self.session, ["20001", "100"])
        self.assertEqual(self.player.boat_state["course"], [19500, 19500])

    def test_port_discovery_and_docking_range(self):
        ocean.command_setport(self.session, ["10", "10", "First", "Harbor"])
        ocean.command_setport(self.session, ["90", "10", "Nearby", "Dock"])
        ocean.buy_boat(self.session)
        with patch.object(commands, "cmd_look"):
            ocean.command_board(self.session, ["boat"])
        ocean.command_dock(self.session, [])
        self.assertIn("Nearby Dock", self.player.boat_state["discovered"])
        ocean.command_dock(self.session, ["Nearby", "Dock"])
        self.assertEqual(self.player.boat_state["docked"], "First Harbor")
        ocean.command_course(self.session, ["50", "10"])
        ocean.tick_boats([self.session], 2)
        ocean.command_dock(self.session, ["Nearby", "Dock"])
        self.assertEqual(self.player.boat_state["docked"], "Nearby Dock")
        with patch.object(commands, "cmd_look"):
            ocean.command_disembark(self.session, [])
        self.assertEqual(self.player.room_vnum, 918211)
        saved = Player.from_dict(self.player.to_dict())
        self.assertEqual(saved.boat_state["discovered"], self.player.boat_state["discovered"])

    def test_port_registration_is_immortal_only(self):
        self.session.account.staff_level = "player"
        ocean.command_setport(self.session, ["10", "10", "Not", "Allowed"])
        self.assertFalse(ocean.ports())


if __name__ == "__main__":
    unittest.main()
