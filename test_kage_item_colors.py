"""20 mission-point legendary items retain identity and gain character-specific xterm colors."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import colors
import commands
import legendary_items
import olc
from models import Player


class KageLegendaryPaletteTests(unittest.TestCase):
    def setUp(self):
        self.prototypes = {
            data["vnum"]: {
                **olc.default_object(data["vnum"], data["short_desc"]),
                "short_desc": data["short_desc"],
                "rarity": "legendary",
                "stat_bonuses": dict(data["stat_bonuses"]),
                "wear_loc": data["wear_loc"],
            }
            for data in legendary_items.LEGENDARY_ITEMS.values()
        }
        p = patch.object(olc, "OBJECT_TEMPLATES", self.prototypes)
        p.start()
        self.addCleanup(p.stop)
        self.player = Player("ColorTester", "ColorTester")
        self.player.village = "leaf"
        self.player.mission_points = 5000
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          send=Mock())
        self.session.active_sessions = lambda: [self.session]

    def test_twenty_distinct_items_each_has_an_independent_two_color_scheme(self):
        roster = legendary_items.LEGENDARY_ITEMS
        self.assertEqual(len(roster), 20)
        self.assertEqual(len(legendary_items.LEGENDARY_COLOR_SCHEMES), 20)
        self.assertEqual(set(legendary_items.LEGENDARY_COLOR_SCHEMES),
                         {data["vnum"] for data in roster.values()})
        self.assertEqual(len(set(legendary_items.LEGENDARY_COLOR_SCHEMES.values())), 20)
        for item in roster.values():
            self.assertEqual(item["cost_mission_points"], 500)
            color_ids = legendary_items.LEGENDARY_COLOR_SCHEMES[item["vnum"]]
            self.assertEqual(len(color_ids), 2)
            self.assertNotEqual(*color_ids)
            self.assertTrue(all(type(n) is int and 0 <= n <= 255 for n in color_ids))
            displayed = legendary_items.styled_name(item["short_desc"])
            self.assertIsNotNone(displayed)
            self.assertTrue(displayed.endswith("&x"))
            self.assertEqual(colors.render(displayed, False), item["short_desc"])
            self.assertEqual(displayed.count("&["), len(item["short_desc"].split()))
            rendered = colors.render(displayed, True)
            for color_id in color_ids:
                self.assertIn(f"\\x1b[38;5;{color_id}m", rendered.encode("unicode_escape").decode())

    def test_hardcoded_templates_are_not_modified_by_display(self):
        item = legendary_items.LEGENDARY_ITEMS["naruto's jacket"]
        proto = self.prototypes[item["vnum"]]
        old = (dict(proto), dict(item))
        displayed = commands.rarity_colored_name(item["short_desc"])
        self.assertIn("&[214]", displayed)
        self.assertEqual((proto, item), old)
        self.assertNotIn("&[", item["short_desc"])

    def test_nonlegendary_items_stay_plain(self):
        self.assertIsNone(legendary_items.styled_name("A Plain Kunai"))
        self.assertEqual(commands.rarity_colored_name("A Plain Kunai"), "A Plain Kunai")
        self.assertEqual(legendary_items.styled_name("Naruto's Orange Jacket counterfeit"), None)

    def test_kage_list_displays_all_unique_colored_names_with_unchanged_prices(self):
        with patch.object(commands, "_own_kage_chamber", return_value=True), \
             patch("village_perks.active_perks_display", return_value=[]):
            commands.cmd_list(self.session, [])
        result = self.session.send.call_args.args[0]
        for item in legendary_items.LEGENDARY_ITEMS.values():
            self.assertIn(legendary_items.styled_name(item["short_desc"]), result)
        self.assertEqual(result.count("500 mission point(s)"), 20)

    def test_inventory_and_equipment_display_colored_without_mutating_saved_names(self):
        item = legendary_items.LEGENDARY_ITEMS["gaara's sand gourd"]
        self.player.inventory = [item["short_desc"]]
        self.player.equipment = {"back": item["short_desc"]}
        old_inventory = list(self.player.inventory)
        commands.cmd_inventory(self.session, [])
        self.assertIn("&[179]Gaara's", self.session.send.call_args.args[0])
        commands.cmd_equipment(self.session, [])
        self.assertIn("&[179]Gaara's", self.session.send.call_args.args[0])
        self.assertEqual(self.player.inventory, old_inventory)
        self.assertEqual(self.player.equipment["back"], item["short_desc"])

    def test_examine_preserves_legendary_rarity_tag_and_custom_name(self):
        item = legendary_items.LEGENDARY_ITEMS["itachi's akatsuki ring"]
        formatted = commands._examine_rarity_colored_name(item["short_desc"])
        self.assertIn("Legendary", colors.render(formatted, False))
        self.assertIn("&[203]Itachi's", formatted)
        self.assertEqual(colors.render(formatted, False), "[Legendary] Itachi's Akatsuki Ring")

    def test_bought_item_remains_a_plain_persistable_name(self):
        item = legendary_items.LEGENDARY_ITEMS["naruto's jacket"]
        with patch.object(commands, "_own_kage_chamber", return_value=True):
            commands.cmd_buy(self.session, ["naruto's", "jacket"])
        self.assertIn(item["short_desc"], self.player.inventory)
        self.assertEqual(self.player.mission_points, 4500)
        result = self.session.send.call_args.args[0]
        self.assertIn("&[214]Naruto's", result)
        self.assertTrue(all("&[" not in name for name in self.player.inventory))


if __name__ == "__main__":
    unittest.main()
