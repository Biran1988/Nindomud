"""Regression coverage for crafted combat durability and idle-character cleanup."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import commands
import equipment_durability as durability
import inactive_player_purge as purge
import olc
import session
import storage
import tool_durability


class DurabilityTests(unittest.TestCase):
    def test_job_tool_display_keeps_counts_out_of_item_names(self):
        self.assertEqual(
            tool_durability.display_name("A Copper Hoe [249/250 uses]"),
            "A Copper Hoe",
        )
        self.assertEqual(tool_durability.uses_left("A Copper Hoe [249/250 uses]"),
                         (249, 250))

    def test_metal_tiers_and_legacy_forge(self):
        for metal, expected in (("iron ingot", 2500),
                                ("steel ingot", 5000),
                                ("chakra steel ingot", 10000)):
            obj = {"item_type": "weapon", "craft_materials": [metal, metal]}
            self.assertEqual(durability.state(obj), (expected, expected))
            durability.initialise(obj)
            self.assertEqual(obj["durability"], expected)
        self.assertIsNone(durability.state({"item_type": "weapon"}))

    def test_weapon_break_frees_vnum_without_changing_item_name(self):
        vnum = 500000
        name = "The Silver Moon"
        obj = {"short_desc": name, "item_type": "weapon",
               "craft_materials": ["iron ingot", "iron ingot"],
               "max_durability": 2500, "durability": 1}
        actor = SimpleNamespace(equipment={"wielded": name})
        messages = []
        s = SimpleNamespace(player=actor, send=messages.append)
        with (patch.dict(olc.OBJECT_TEMPLATES, {vnum: obj}, clear=True),
              patch.object(commands, "_NEXT_CRAFTED_ITEM_VNUM", 500001),
              patch.object(storage, "save_player"),
              patch("world_autosave.mark_dirty")):
            self.assertTrue(durability.wear_weapon(s))
            self.assertIsNone(actor.equipment["wielded"])
            self.assertNotIn(vnum, olc.OBJECT_TEMPLATES)
            self.assertEqual(commands._allocate_crafted_item_vnum(), vnum)
        self.assertIn(name, " ".join(messages))

    def test_armor_only_wears_on_chance(self):
        name = "Mystic Hauberk"
        actor = SimpleNamespace(equipment={"body": name})
        s = SimpleNamespace(player=actor, send=lambda _: None)
        obj = {"short_desc": name, "item_type": "armor",
               "craft_materials": ["steel ingot", "steel ingot"],
               "max_durability": 5000, "durability": 7}
        with (patch.dict(olc.OBJECT_TEMPLATES, {500009: obj}, clear=True),
              patch.object(storage, "save_player"),
              patch("world_autosave.mark_dirty"),
              patch.object(durability.random, "randint", side_effect=[11, 10]),
              patch.object(durability.random, "choice", return_value=("body", name))):
            self.assertFalse(durability.wear_armor(s))
            self.assertTrue(durability.wear_armor(s))
            self.assertEqual(obj["durability"], 6)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp()
        self.players = os.path.join(self.temp.name, "players")
        os.makedirs(self.players)
        self.patches = [
            patch.object(storage, "PLAYERS_DIR", self.players),
            patch.object(storage, "DATA_DIR", self.temp.name),
            patch.object(storage, "ensure_dirs"),
            patch.object(storage, "load_account",
                         return_value=SimpleNamespace(staff_level="player")),
            patch.object(storage, "delete_character"),
            patch.object(session, "ACTIVE_SESSIONS", []),
        ]
        self.mocks = [p.start() for p in self.patches]
        for p in self.patches:
            self.addCleanup(p.stop)

    def add_player(self, name, level, y, mo, day):
        stamp = datetime(y, mo, day, tzinfo=timezone.utc).timestamp()
        with open(os.path.join(self.players, name.lower() + ".json"), "w") as f:
            json.dump({"account_name": name, "level": level,
                       "last_login_at": stamp}, f)

    def test_inactivity_levels_and_exemption(self):
        self.add_player("Student", 49, 2026, 4, 1)
        self.add_player("Chunin", 60, 2026, 1, 1)
        self.add_player("Veteran", 100, 2025, 10, 1)
        self.add_player("Active", 100, 2026, 6, 1)
        self.add_player("Elder", 250, 2020, 1, 1)
        deleted = purge.purge_inactive(self.now)
        self.assertEqual(deleted, ["chunin", "student", "veteran"])
        self.assertEqual(self.mocks[4].call_count, 3)
        self.assertNotIn("elder", deleted)

    def test_connected_never_purged(self):
        self.add_player("StillHere", 1, 2020, 1, 1)
        connection = SimpleNamespace(player=SimpleNamespace(name="StillHere"))
        with patch.object(session, "ACTIVE_SESSIONS", [connection]):
            self.assertEqual(purge.purge_inactive(self.now), [])
        self.mocks[4].assert_not_called()


if __name__ == "__main__":
    unittest.main()
