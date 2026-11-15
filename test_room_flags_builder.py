"""Room flags unify apartment, player-shop and biome; builders list flags."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import olc
import world
import combat
import room_flags
from models import Player


class RoomFlagBuilderTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("FlagTester", "FlagTester", room_vnum=997700)
        self.s = NS(player=self.player, account=NS(staff_level="implementor"), send=Mock())
        self.room = world.Room(997700, "Flag Room", "Testing")
        self.room_map = patch.dict(world.WORLD.rooms, {997700: self.room})
        self.room_map.start()
        self.addCleanup(self.room_map.stop)
        self.audit = patch.object(olc, "_log")
        self.audit.start()
        self.addCleanup(self.audit.stop)

    def rset(self, *args):
        olc.cmd_rset(self.s, list(args))
        return self.s.send.call_args.args[0]

    def test_apartment_single_flag_and_no_legacy_on_off(self):
        self.rset("flags", "apartment")
        self.assertIn("apartment", self.room.flags)
        self.assertTrue(self.room.apartment)
        self.rset("apartment", "off")
        self.assertTrue(self.room.apartment)
        self.rset("flags", "apartment")
        self.assertFalse(self.room.apartment)
        self.assertNotIn("apartment", self.room.flags)

    def test_owned_room_removal_guard_and_no_apartment_shop_overlap(self):
        self.rset("flags", "apartment")
        self.room.owner = "Owned"
        self.assertIn("owner must sell", self.rset("flags", "apartment"))
        self.assertTrue(self.room.apartment)
        self.room.owner = None
        self.assertIn("Remove the apartment", self.rset("flags", "playershop"))
        self.rset("flags", "apartment")
        self.rset("flags", "playershop")
        self.assertTrue(self.room.player_shop)
        self.assertIn("player_shop", self.room.flags)
        self.room.owner = "ShopOwner"
        self.assertIn("owner must sell", self.rset("flags", "playershop"))
        self.assertTrue(self.room.player_shop)

    def test_biomes_replaced_and_cleared(self):
        self.rset("flags", "forest")
        self.assertIn("biome_forest", self.room.flags)
        self.assertEqual(self.room.biome, "forest")
        self.rset("flags", "biome_mountain")
        self.assertNotIn("biome_forest", self.room.flags)
        self.assertIn("biome_mountain", self.room.flags)
        self.assertEqual(self.room.biome, "mountain")
        self.rset("flags", "mountain")
        self.assertEqual(self.room.biome, "none")
        self.assertFalse([x for x in self.room.flags if x.startswith("biome_")])
        self.assertIn("Unknown room flag", self.rset("flags", "biome_none"))
        self.rset("biome", "forest")
        self.assertEqual(self.room.biome, "none")

    def test_room_short_name_flags_and_flags_no_argument_options(self):
        self.rset("flags", "acceleratedhealing")
        self.assertIn("accelerated_healing", self.room.flags)
        self.rset("flags", "CapturePoint")
        self.assertIn("CapturePoint", self.room.flags)
        text = self.rset("flags")
        self.assertIn("Current", text)
        self.assertIn("biome_forest", text)
        self.assertIn("apartment", text)
        self.assertIn("player_shop", text)

    def test_existing_legacy_room_values_upgrade_on_load(self):
        old = world.Room(997701, "Old", "Saved", apartment=True,
                         biome="swamp", safe=True)
        self.assertTrue(old.apartment)
        self.assertIn("apartment", old.flags)
        self.assertIn("biome_swamp", old.flags)
        self.assertIn("safe", old.flags)


class FlagsOptionsTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("MobFlagTest", "MobFlagTest")
        self.s = NS(player=self.player, account=NS(staff_level="implementor"), send=Mock())
        self.mob = patch.dict(combat.MOB_TEMPLATES, {997702: combat.default_template(997702, "test mob")})
        self.obj = patch.dict(olc.OBJECT_TEMPLATES, {997703: olc.default_object(997703, "test object")})
        for ctx in (self.mob, self.obj, patch.object(olc, "_log")):
            ctx.start()
            self.addCleanup(ctx.stop)

    def test_mob_flags_lists_real_valid_values_without_argument(self):
        olc.cmd_mset(self.s, ["997702", "flags"])
        text = self.s.send.call_args.args[0]
        self.assertIn("Valid mob flags", text)
        self.assertIn("Banker", text)
        self.assertIn("ShopGeneral", text)
        self.assertIn("Current", text)

    def test_object_flags_lists_real_valid_values_without_argument(self):
        olc.cmd_oset(self.s, ["997703", "flags"])
        text = self.s.send.call_args.args[0]
        self.assertIn("Valid item flags", text)
        self.assertIn("AutoBalance", text)
        self.assertIn("Current", text)


if __name__ == "__main__":
    unittest.main()
