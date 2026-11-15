"""Equipment slot regressions: paired jewelry, alias construction and saved gear."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import item_balance
import olc
import world
from models import Player


class JewelrySlotsTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("JewelryTester", "JewelryTester", room_vnum=993200, level=100)
        self.player.inventory = []
        self.s = NS(account=NS(staff_level="implementor"),
                    player=self.player, send=Mock())
        self.rooms = patch.object(world.WORLD, "rooms",
                                  {993200: world.Room(993200, "Jewelry Shop", "Jewelry shop.")})
        self.items = patch.object(olc, "OBJECT_TEMPLATES", {})
        self.logs = patch.object(olc, "_log")
        self.emits = patch("room_actions.emit")
        for ctx in (self.rooms, self.items, self.logs, self.emits):
            ctx.start()
            self.addCleanup(ctx.stop)

    def item(self, vnum, name, wear_loc, bonuses=None):
        proto = olc.default_object(vnum, name)
        proto.update(item_type="armor", wear_loc=wear_loc, level=75,
                     stat_bonuses=bonuses or {})
        olc.OBJECT_TEMPLATES[vnum] = proto
        return name

    def wear(self, name):
        commands.cmd_wear(self.s, name.split())

    def test_two_identical_rings_equip_and_remove_individually(self):
        ring = self.item(993211, "A Silver Ring", "finger",
                         {"max_health": 20})
        self.player.inventory = [ring, ring, ring]
        starting = self.player.maximum_health
        self.wear("silver ring")
        self.assertEqual(self.player.equipment["finger"], ring)
        self.wear("silver ring")
        self.assertEqual(self.player.equipment["finger2"], ring)
        self.assertEqual(self.player.maximum_health, starting + 40)
        self.wear("silver ring")
        self.assertEqual(self.player.inventory.count(ring), 1)
        self.assertEqual(self.player.maximum_health, starting + 40)
        commands.cmd_remove(self.s, ["ring2"])
        self.assertNotIn("finger2", self.player.equipment)
        self.assertEqual(self.player.maximum_health, starting + 20)
        self.assertEqual(self.player.inventory.count(ring), 2)

    def test_earrings_and_bracelets_fill_two_slots_via_wear_all(self):
        earring = self.item(993212, "A Jade Earring", "ear")
        bracelet = self.item(993213, "A Blue Bracelet", "wrist")
        self.player.inventory = [earring, earring, earring, bracelet, bracelet]
        commands.cmd_wear(self.s, ["all"])
        self.assertEqual([self.player.equipment[k] for k in ("ear", "ear2")],
                         [earring, earring])
        self.assertEqual([self.player.equipment[k] for k in ("wrist", "wrist2")],
                         [bracelet, bracelet])
        self.assertEqual(self.player.inventory, [earring])
        commands.cmd_equipment(self.s, [])
        output = self.s.send.call_args.args[0]
        self.assertIn("<ear2>", output)
        self.assertIn("<finger2>", output)
        self.assertIn("<wrist2>", output)
        self.assertIn("<nose>", output)
        self.assertIn("<neck>", output)

    def test_nose_neck_and_existing_piercing_do_not_conflict(self):
        for vnum, name, slot in (
            (993214, "A Gold Necklace", "neck"),
            (993215, "A Nose Stud", "nose"),
            (993216, "A Facial Piercing", "piercing"),
        ):
            self.player.inventory.append(self.item(vnum, name, slot))
            self.wear(name)
        self.assertEqual(set(self.player.equipment), {"neck", "nose", "piercing"})

    def test_builder_wear_location_aliases(self):
        vnum = 993217
        olc.cmd_ocreate(self.s, [str(vnum), "A", "Small", "Ring"])
        olc.cmd_oset(self.s, [str(vnum), "itemtype", "armor"])
        for alias, expected in (
            ("ring", "finger"), ("earring", "ear"), ("bracelet", "wrist"),
            ("necklace", "neck"), ("nose piercing", "nose"),
            ("ring2", "finger2"), ("earring2", "ear2"),
            ("bracelet2", "wrist2")
        ):
            with self.subTest(alias=alias):
                olc.cmd_oset(self.s, [str(vnum), "wearloc", *alias.split()])
                self.assertEqual(olc.OBJECT_TEMPLATES[vnum]["wear_loc"], expected)
        olc.cmd_oset(self.s, [str(vnum), "level", "50"])
        self.assertTrue(item_balance.active(olc.OBJECT_TEMPLATES[vnum]))

    def test_single_legacy_finger_slot_load_still_works(self):
        item = self.item(993218, "An Old Signet", "finger")
        self.player.equipment = {"finger": item, "neck": "An Existing Necklace"}
        self.player.inventory = [item]
        commands.cmd_wear(self.s, ["old", "signet"])
        self.assertEqual(self.player.equipment["finger"], item)
        self.assertEqual(self.player.equipment["finger2"], item)
        self.assertEqual(self.player.equipment["neck"], "An Existing Necklace")

    def test_explicit_second_slot_is_not_redirected(self):
        item = self.item(993219, "A Right Earring", "ear2")
        self.player.inventory = [item]
        self.wear("right earring")
        self.assertNotIn("ear", self.player.equipment)
        self.assertEqual(self.player.equipment["ear2"], item)


if __name__ == "__main__":
    unittest.main()
