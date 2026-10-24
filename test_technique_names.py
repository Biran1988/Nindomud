"""Old learned moves, scrolls and mastery survive the corrected name."""
import os
import tempfile
import unittest
from unittest.mock import patch

import commands
import data_jutsu
import olc
import storage
import technique_names as names
from models import Player


class TechniqueNameTests(unittest.TestCase):
    def test_old_save_migrates_mastery_practice_cooldown_and_scrolls(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(storage, "DATA_DIR", folder), \
             patch.object(storage, "PLAYERS_DIR", os.path.join(folder, "players")), \
             patch.object(storage, "ACCOUNTS_DIR", os.path.join(folder, "accounts")):
            p = Player("OldNinja", "OldNinja", level=100)
            p.learned_skills = p.practiced_skills = p.practice_exempt_skills = [names.OLD_NAME]
            p.skill_proficiencies = {names.OLD_NAME: 150}
            p.signature_move = names.OLD_NAME
            p.cooldowns[names.OLD_KEY] = 9999999999
            p.inventory = ["A Scroll of " + names.OLD_NAME]
            p.backpack_contents = {"0": ["A Scroll of " + names.OLD_NAME]}
            storage.save_player(p)
            loaded = storage.load_player(p.name)
            self.assertIn(names.NEW_NAME, loaded.learned_skills)
            self.assertEqual(loaded.skill_proficiencies[names.NEW_NAME], 150)
            self.assertEqual(loaded.signature_move, names.NEW_NAME)
            self.assertEqual(loaded.cooldowns[names.NEW_KEY], 9999999999)
            self.assertNotIn(names.OLD_NAME, loaded.skill_proficiencies)
            self.assertEqual(loaded.inventory, ["A Scroll of " + names.NEW_NAME])
            self.assertEqual(loaded.backpack_contents["0"], loaded.inventory)
            self.assertEqual(storage.load_player(p.name).skill_proficiencies[names.NEW_NAME], 150)

    def test_old_command_and_old_scroll_name_still_resolve(self):
        key, consumed = data_jutsu.match_prefix("100 years of death Bandit".lower().split())
        self.assertEqual((key, consumed), (names.NEW_KEY, 4))
        proto = olc.default_object(9810, "A Scroll of " + names.OLD_NAME)
        proto["scroll_jutsu"] = names.OLD_KEY
        with patch.object(olc, "OBJECT_TEMPLATES", {9810: proto}):
            names.migrate_templates()
            self.assertEqual(proto["short_desc"], "A Scroll of " + names.NEW_NAME)
            self.assertEqual(proto["scroll_jutsu"], names.NEW_KEY)
            self.assertIs(commands._find_object_prototype_by_name("A Scroll of " + names.OLD_NAME), proto)


if __name__ == "__main__":
    unittest.main()
