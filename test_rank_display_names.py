"""Regressions: player-facing rank names and saved headband compatibility."""
import unittest

import commands
import data_headbands
import kage
import prompt
from models import Player


class StandardNinjaRankNamesTests(unittest.TestCase):
    def test_display_rank_and_kage_title(self):
        for stored, label in (("chunin", "Chuunin"),
                              ("special jonin", "Special Jounin"),
                              ("jonin", "Jounin")):
            with self.subTest(rank=stored):
                p = Player("Ninja", "Ninja", village_rank=stored)
                self.assertEqual(kage.display_rank(p), label)
                p.is_kage = True
                self.assertEqual(kage.display_rank(p), label + " (Kage)")
                self.assertIn(stored, kage.RANK_LEVEL_CAPS)

    def test_who_labels_and_width(self):
        self.assertEqual(commands.RANK_WHO_LABEL["chunin"], "Chuunin")
        self.assertEqual(commands.RANK_WHO_LABEL["special jonin"], "Sp.Jounin")
        self.assertEqual(commands.RANK_WHO_LABEL["jonin"], "Jounin")
        self.assertGreaterEqual(commands.WHO_RANK_WIDTH,
                                max(map(len, commands.RANK_WHO_LABEL.values())))

    def test_prompt_rank_token(self):
        p = Player("Ninja", "Ninja", village_rank="special jonin")
        p.prompt_string = "%k"
        self.assertEqual(prompt.render_prompt(p), "Special Jounin")

    def test_new_headband_names_and_old_saved_items(self):
        self.assertEqual(data_headbands.headband_base_name("Konoha", "chunin"),
                         "A Konoha Chuunin Headband")
        self.assertEqual(data_headbands.headband_base_name("Konoha", "jonin"),
                         "A Konoha Jounin Headband")
        p = Player.from_dict({
            "name": "Legacy", "account_name": "Legacy",
            "village_rank": "chunin",
            "equipment": {"head": "A Konoha Chunin Headband"},
            "inventory": ["A Konoha Special Jonin Headband"],
            "storage_room_items": ["A Konoha Jonin Headband"],
            "backpack_contents": {"0": ["A Konoha Chunin Headband"]},
            "shop_stock": [{"item_name": "A Konoha Jonin Headband", "price": 10}],
        })
        self.assertEqual(p.village_rank, "chunin")
        self.assertEqual(p.equipment["head"], "A Konoha Chuunin Headband")
        self.assertEqual(p.inventory[0], "A Konoha Special Jounin Headband")
        self.assertEqual(p.storage_room_items[0], "A Konoha Jounin Headband")
        self.assertEqual(p.backpack_contents["0"][0], "A Konoha Chuunin Headband")
        self.assertEqual(p.shop_stock[0]["item_name"], "A Konoha Jounin Headband")


if __name__ == "__main__":
    unittest.main()
