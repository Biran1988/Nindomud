"""Builder list commands: default current area and explicit global ALL."""

from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import patch

import olc


class BuilderAreaListTests(TestCase):
    def setUp(self):
        self.messages = []
        self.session = NS(player=NS(room_vnum=150), send=self.messages.append)
        self.area = NS(name="leaf", vnum_start=100, vnum_end=199)
        self.rooms = {
            110: NS(name="Leaf square", ground_items=["Ground Scroll"]),
            150: NS(name="Leaf apartment", ground_items=[]),
            210: NS(name="Stone square", ground_items=["Stone Flag"]),
        }
        self.mobs = {
            110: [NS(template_vnum=8001)],
            210: [NS(template_vnum=8002)],
        }
        self.mob_templates = {
            8000: {"short_desc": "Leaf patrol", "level": 5},
            8001: {"short_desc": "Leaf merchant", "level": 10, "shop_items": [9002]},
            8002: {"short_desc": "Stone guard", "level": 20},
            8003: {"short_desc": "Unplaced mob", "level": 1},
        }
        self.objects = {
            9000: {"short_desc": "Leaf Banner", "item_type": "trash"},
            9001: {"short_desc": "Ground Scroll", "item_type": "scroll"},
            9002: {"short_desc": "Shop Potion", "item_type": "potion"},
            9003: {"short_desc": "Stone Flag", "item_type": "trash"},
            9004: {"short_desc": "Unplaced item", "item_type": "trash"},
        }
        self.points = [
            {"kind": "mob", "vnum": 8000, "room_vnum": 110},
            {"kind": "item", "vnum": 9000, "room_vnum": 110},
            {"kind": "mob", "vnum": 8002, "room_vnum": 210},
            {"kind": "item", "vnum": 9003, "room_vnum": 210},
        ]

    def run_list(self, command, args=(), area="current"):
        area_value = self.area if area == "current" else area
        self.messages.clear()
        with patch.object(olc, "_require_builder", return_value=True), \
             patch.object(olc.areas, "find_area_for_vnum", return_value=area_value), \
             patch.object(olc.world.WORLD, "rooms", self.rooms), \
             patch.object(olc.combat, "MOBS_BY_ROOM", self.mobs), \
             patch.object(olc.combat, "MOB_TEMPLATES", self.mob_templates), \
             patch.object(olc, "OBJECT_TEMPLATES", self.objects), \
             patch.object(olc.spawn_points, "list_spawn_points", return_value=self.points):
            getattr(olc, "cmd_" + command)(self.session, list(args))
        return "\n".join(self.messages)

    def test_mlist_defaults_to_area_spawns_and_current_mobs(self):
        output = self.run_list("mlist")
        self.assertIn("Mobile prototypes in leaf:", output)
        self.assertIn("8000: Leaf patrol", output)
        self.assertIn("8001: Leaf merchant", output)
        self.assertNotIn("8002: Stone guard", output)
        self.assertNotIn("8003: Unplaced mob", output)

    def test_olist_uses_spawns_ground_items_and_local_shops(self):
        output = self.run_list("olist")
        self.assertIn("Object prototypes in leaf:", output)
        for vnum in (9000, 9001, 9002):
            self.assertIn(str(vnum) + ":", output)
        for vnum in (9003, 9004):
            self.assertNotIn(str(vnum) + ":", output)

    def test_all_commands_show_global_prototypes_and_rooms(self):
        for command, wanted in (
            ("mlist", "8003: Unplaced mob"),
            ("olist", "9004: Unplaced item"),
            ("rlist", "210: Stone square"),
        ):
            with self.subTest(command=command):
                output = self.run_list(command, ["all"])
                self.assertIn("(all areas):", output)
                self.assertIn(wanted, output)

    def test_all_with_vnum_range_filters_globally(self):
        output = self.run_list("mlist", ["all", "8002", "8003"])
        self.assertIn("8002: Stone guard", output)
        self.assertIn("8003: Unplaced mob", output)
        self.assertNotIn("8001: Leaf merchant", output)
        output = self.run_list("rlist", ["all", "200", "300"])
        self.assertIn("210: Stone square", output)
        self.assertNotIn("110: Leaf square", output)

    def test_explicit_range_stays_scoped_to_current_area(self):
        output = self.run_list("mlist", ["8001", "8003"])
        self.assertIn("8001: Leaf merchant", output)
        self.assertNotIn("8002: Stone guard", output)
        output = self.run_list("olist", ["9001", "9003"])
        self.assertIn("9001: Ground Scroll", output)
        self.assertNotIn("9003: Stone Flag", output)

    def test_all_works_without_registered_area(self):
        output = self.run_list("olist", ["all"], area=None)
        self.assertIn("9004: Unplaced item", output)
        output = self.run_list("olist", area=None)
        self.assertIn("isn't within any registered area", output)

    def test_bad_args_show_usage(self):
        for command in ("mlist", "olist", "rlist"):
            with self.subTest(command=command):
                output = self.run_list(command, ["all", "junk"])
                self.assertIn(
                    f"Usage: {command} [all] [low_vnum high_vnum]", output
                )

    def test_ambiguous_ground_item_name_does_not_claim_other_prototypes(self):
        self.objects[9050] = {"short_desc": "Ground Scroll", "item_type": "scroll"}
        output = self.run_list("olist")
        self.assertNotIn("9001:", output)
        self.assertNotIn("9050:", output)
