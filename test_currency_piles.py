"""Physical Ryo pile transfers and auto-persistence without area-file edits."""
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import currency_piles
import storage
import world
import world_persistence
from models import Player


class PhysicalRyoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.patches = [
            patch.object(storage, "DATA_DIR", temporary.name),
            patch.object(world.WORLD, "rooms", {}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.room = world.Room(7111, "Market Street", "A busy market.")
        self.other_room = world.Room(7112, "Town Gate", "The village gate.")
        world.WORLD.add_room(self.room)
        world.WORLD.add_room(self.other_room)
        owner = Player("Ninja", "Ninja", room_vnum=7111)
        owner.ryo = 2000
        receiver = Player("Ally", "Ally", room_vnum=7111)
        self.session = NS(player=owner, send=Mock(), broadcast_room=Mock(),
                          account=NS(staff_level="player"), state=NS(name="PLAYING"))
        self.receiver = NS(player=receiver, send=Mock(), broadcast_room=Mock(),
                           account=NS(staff_level="player"), state=NS(name="PLAYING"))
        for session in (self.session, self.receiver):
            session.active_sessions = lambda: [self.session, self.receiver]

    def test_drop_exact_amount_appears_as_physical_room_pile(self):
        commands.cmd_drop(self.session, ["750", "ryo"])
        self.assertEqual(self.session.player.ryo, 1250)
        self.assertEqual(self.room.ground_ryo, [750])
        self.assertEqual(self.session.send.call_args.args[0], "You drop a pile of 750 Ryo.")
        with open(currency_piles._ledger_path(), encoding="utf-8") as f:
            self.assertIn('"7111"', f.read())
        self.session.send.reset_mock()
        commands.cmd_look(self.session, [])
        self.assertTrue(any("750 Ryo" in c.args[0] for c in self.session.send.call_args_list))

    def test_get_specific_and_all_piles_returns_their_full_value(self):
        commands.cmd_drop(self.session, ["500", "ryo"])
        commands.cmd_drop(self.session, ["700", "ryo"])
        self.assertEqual(self.room.ground_ryo, [500, 700])
        commands.cmd_get(self.session, ["2.ryo"])
        self.assertEqual(self.session.player.ryo, 1500)
        self.assertEqual(self.room.ground_ryo, [500])
        commands.cmd_get(self.session, ["500", "ryo"])
        self.assertEqual(self.session.player.ryo, 2000)
        self.assertEqual(self.room.ground_ryo, [])
        commands.cmd_drop(self.session, ["300", "ryo"])
        commands.cmd_drop(self.session, ["200", "ryo"])
        commands.cmd_get(self.session, ["all", "ryo"])
        self.assertEqual(self.session.player.ryo, 2000)
        self.assertEqual(self.room.ground_ryo, [])

    def test_give_ryo_directly_between_players_in_the_same_room(self):
        commands.cmd_give(self.session, ["250", "ryo", "Ally"])
        self.assertEqual(self.session.player.ryo, 1750)
        self.assertEqual(self.receiver.player.ryo, 250)
        self.assertIn("gives you 250 Ryo", self.receiver.send.call_args.args[0])
        commands.cmd_give(self.session, ["all", "ryo", "to", "Ally"])
        self.assertEqual(self.session.player.ryo, 0)
        self.assertEqual(self.receiver.player.ryo, 2000)

    def test_rejects_invalid_and_insufficient_amounts_without_minting(self):
        for amount in ("0", "-10", "3000", "1.5"):
            commands.cmd_drop(self.session, [amount, "ryo"])
            commands.cmd_give(self.session, [amount, "ryo", "Ally"])
        self.assertEqual(self.session.player.ryo, 2000)
        self.assertEqual(self.receiver.player.ryo, 0)
        self.assertEqual(self.room.ground_ryo, [])
        self.receiver.player.room_vnum = 7112
        commands.cmd_give(self.session, ["100", "ryo", "Ally"])
        self.assertEqual(self.session.player.ryo, 2000)
        self.assertEqual(self.receiver.player.ryo, 0)

    def test_saved_piles_survive_restart_without_touching_world_snapshots(self):
        commands.cmd_drop(self.session, ["75", "ryo"])
        state = world_persistence.snapshot_world()
        self.assertNotIn("ground_ryo", state["rooms"]["7111"])
        self.room.ground_ryo.clear()
        currency_piles.restore_piles()
        self.assertEqual(self.room.ground_ryo, [75])
        commands.cmd_get(self.receiver, ["ryo"])
        self.assertEqual(self.receiver.player.ryo, 75)
        self.assertEqual(self.room.ground_ryo, [])
        currency_piles.restore_piles()
        self.assertEqual(self.room.ground_ryo, [])

    def test_currency_pickup_ignores_item_slot_caps(self):
        self.receiver.player.inventory = [f"Unique Item {x}" for x in range(20)]
        commands.cmd_drop(self.session, ["80", "ryo"])
        commands.cmd_get(self.receiver, ["ryo"])
        self.assertEqual(self.receiver.player.ryo, 80)
        self.assertEqual(len(self.receiver.player.inventory), 20)
        self.assertFalse(self.room.ground_ryo)


if __name__ == "__main__":
    unittest.main()
