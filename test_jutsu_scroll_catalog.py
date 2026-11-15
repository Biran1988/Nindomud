"""Builder scroll-area population, ordered class VNUMs and legacy migration."""
import copy
import tempfile
import unittest
from unittest.mock import patch

import combat
import content
import data_jutsu
import jutsu_scroll_catalog as catalog
import olc
import reaper_seal
import storage
import world_persistence


class ScrollJutsuCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for obj, name, value in (
            (storage, "DATA_DIR", self.tmp.name),
            (olc, "OBJECT_TEMPLATES", {}),
            (combat, "MOB_TEMPLATES", {}),
        ):
            context = patch.object(obj, name, value)
            context.start()
            self.addCleanup(context.stop)

    def test_full_registered_scroll_catalog_is_ordered_general_first(self):
        entries = catalog.entries()
        self.assertEqual(len(entries), len(data_jutsu.JUTSU) - 1 + 4)
        self.assertEqual(entries[0][0], 31501)
        self.assertEqual(entries[-1][0], 31759)
        self.assertEqual([n for n, _, _ in entries], list(range(31501, 31760)))
        original = entries[:235]
        self.assertEqual([d["class_requirement"] for _, _, d in original],
                         sorted([d["class_requirement"] for _, _, d in original],
                                key=catalog.CLASS_ORDER.index))
        for cls in catalog.CLASS_ORDER:
            group = [d["display_name"].casefold() for _, _, d in original
                     if d["class_requirement"] == cls]
            self.assertEqual(group, sorted(group))
        # New techniques are appended after the released 235: insertion
        # into the original General block would invalidate live scroll IDs.
        self.assertEqual([key for _, key, _ in entries[235:239]],
                         ["elemental shield", "fortress barrier", "reinforced barrier", "sanctuary"])
        self.assertEqual([key for _, key, _ in entries[239:243]],
                         ["second attack", "third attack", "fourth attack", "fifth attack"])
        self.assertEqual(len(entries[243:]), 16)
        # All new technique scrolls are appended, never inserted into released IDs.
        import anime_arts
        self.assertEqual({key for _, key, _ in entries[243:]},
                         set(anime_arts.jutsu_entries()))
        self.assertEqual({name: catalog.vnum_for(name) for name in
                          ("second attack", "third attack", "fourth attack", "fifth attack")},
                         {"second attack": 31740, "third attack": 31741,
                          "fourth attack": 31742, "fifth attack": 31743})
        self.assertNotIn("tailed beast bomb", [key for _, key, _ in entries])
        self.assertEqual(len(set(key for _, key, _ in entries)), len(entries))

    def test_legacy_scrolls_relocate_and_keep_item_names(self):
        expected = {9810: 31501, 9812: 31502, 9771: 31550,
                    9750: 31606, 9821: 31537}
        self.assertEqual(catalog.legacy_vnums(), expected)
        self.assertEqual(reaper_seal.SCROLL_VNUM, expected[9821])
        for old, new in expected.items():
            self.assertTrue(catalog.START_VNUM <= new <= catalog.END_VNUM)
        self.assertEqual(content._ITEM_VNUMS["info_scroll"], 9811)
        self.assertEqual(content._ITEM_VNUMS_EXAM,
                         {"heaven_scroll": 20800, "earth_scroll": 20801})
        self.assertEqual(content._ITEM_VNUMS["genin_study_scroll"], 31606)
        self.assertEqual(content._ITEM_VNUMS["track_scroll"], 31550)
        self.assertEqual(content._ITEM_VNUMS["death_scroll"], 31501)
        self.assertEqual(content._ITEM_VNUMS["advanced_clone_scroll"], 31502)

    def test_register_all_scrolls_without_rooms_or_autospawns(self):
        outcome = catalog.install(migrate_saved=False)
        self.assertEqual(outcome["total"], 259)
        self.assertEqual(outcome["created"], 259)
        self.assertEqual(outcome["conflicts"], ())
        self.assertEqual(len(olc.OBJECT_TEMPLATES), 259)
        for vnum, key, data in catalog.entries():
            obj = olc.OBJECT_TEMPLATES[vnum]
            self.assertEqual(obj["item_type"], "scroll")
            self.assertEqual(obj["scroll_jutsu"], key)
            self.assertEqual(obj["short_desc"], catalog.name_for(key))
        self.assertEqual(olc.OBJECT_TEMPLATES[catalog.vnum_for("advanced shadow clone jutsu")]["cost"], 15000)
        self.assertEqual(olc.OBJECT_TEMPLATES[catalog.vnum_for("track")]["cost"], 500)
        self.assertEqual(catalog.install(migrate_saved=False)["created"], 0)
        self.assertFalse(storage.load_spawn_points())
        self.assertFalse(storage.load_world_state())

    def test_old_saved_scroll_moves_with_edit_and_spawns_while_protecting_area(self):
        old, new = 9771, 31550
        saved = olc.default_object(old, catalog.name_for("track"))
        saved.update(item_type="scroll", scroll_jutsu="track", cost=123456,
                     description="Builder edited track scroll", rarity="epic")
        custom = olc.default_object(31990, "Builder's map")
        custom.update(item_type="misc", description="Do not overwrite me")
        initial_world = {"rooms": {"31501": {"vnum": 31501, "name": "Scroll Hall"}},
                         "items": {str(old): saved, "31990": custom},
                         "mobs": {"111": {"shop_items": [old, 9811]}}}
        storage.save_world_state(copy.deepcopy(initial_world))
        storage.save_spawn_points({"points": {"item:9771:31501":
                                  {"kind": "item", "vnum": 9771, "room_vnum": 31501,
                                   "total_cap": 3, "per_period_cap": 1}}})
        storage.save_custom_templates({"mobs": {}, "items": {str(old): saved}})
        olc.OBJECT_TEMPLATES.update({old: copy.deepcopy(saved),
                                     31990: copy.deepcopy(custom)})
        combat.MOB_TEMPLATES[111] = {"shop_items": [old, 9811]}
        result = catalog.install()
        self.assertEqual(result["total"], 259)
        self.assertEqual(result["moved"], ((9771, 31550),))
        self.assertNotIn(old, olc.OBJECT_TEMPLATES)
        moved = olc.OBJECT_TEMPLATES[new]
        self.assertEqual(moved["cost"], 123456)
        self.assertEqual(moved["description"], "Builder edited track scroll")
        self.assertEqual(olc.OBJECT_TEMPLATES[31990], custom)
        self.assertEqual(combat.MOB_TEMPLATES[111]["shop_items"], [31550, 9811])
        saved_points = storage.load_spawn_points()["points"]
        self.assertNotIn("item:9771:31501", saved_points)
        self.assertEqual(saved_points["item:31550:31501"]["total_cap"], 3)
        self.assertEqual(storage.load_custom_templates()["items"].get("9771"), None)
        self.assertIn("31550", storage.load_custom_templates()["items"])
        persisted = storage.load_world_state()
        self.assertEqual(persisted["rooms"], initial_world["rooms"])
        self.assertEqual(persisted["items"]["31990"], custom)
        self.assertNotIn("9771", persisted["items"])
        self.assertEqual(persisted["items"]["31550"]["cost"], 123456)
        self.assertEqual(persisted["mobs"]["111"]["shop_items"], [31550, 9811])
        self.assertEqual(catalog.install()["moved"], ())

    def test_occupied_target_is_never_overwritten_and_old_scroll_stays(self):
        conflicting_vnum = catalog.vnum_for("track")
        original = olc.default_object(conflicting_vnum, "Builder's Unique Scroll")
        original.update(item_type="scroll", scroll_jutsu="some other spell")
        old = olc.default_object(9771, "A Track Scroll")
        old.update(item_type="scroll", scroll_jutsu="track")
        olc.OBJECT_TEMPLATES.update({conflicting_vnum: original, 9771: old})
        with patch("builtins.print"):
            result = catalog.install(migrate_saved=False)
        self.assertIn(conflicting_vnum, result["conflicts"])
        self.assertEqual(olc.OBJECT_TEMPLATES[conflicting_vnum], original)
        self.assertEqual(olc.OBJECT_TEMPLATES[9771], old)

    def test_copies_already_in_inventory_still_match_new_prototype(self):
        import commands
        from models import Player
        catalog.install(migrate_saved=False)
        player = Player("ScrollBearer", "ScrollBearer")
        player.inventory = ["A Track Scroll", "A Genin Study Scroll",
                            "An Advanced Shadow Clone Scroll"]
        for name, key in zip(player.inventory, ("track", "shadow shuriken technique",
                                               "advanced shadow clone jutsu")):
            self.assertEqual(commands._find_object_prototype_by_name(name)["scroll_jutsu"], key)


if __name__ == "__main__":
    unittest.main()
