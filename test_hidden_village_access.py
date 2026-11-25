"""Regression checks for shared hidden starting-village access."""
import os
import unittest
from unittest.mock import patch
import areas
import content
import data_villages
import data_clans
import village_access
import world
import test_whirlpool
from session import State

class HiddenVillageAccessTests(test_whirlpool.WhirlpoolTests):
    def test_additional_villages_hidden_and_password_gated(self):
        content.populate()
        for key, info in data_villages.VILLAGES.items():
            if "area_key" not in info or info.get("retired_at_creation"):
                continue
            with self.subTest(key=key):
                s, out = self.session()
                self.assertNotIn(key, data_villages.village_names_display().lower())
                self.assertFalse(areas.find_area(info["area_key"]).prototype)
                self.assertIsNotNone(world.WORLD.get(info["starting_room_vnum"]))
                s.handle_line(info["village_name"])
                self.assertIs(s.state, State.CHARGEN_WHIRLPOOL_ACCESS)
                self.assertIsNone(s._pending_village)
                with patch.object(village_access,"verify_whirlpool_access_code",return_value=True):
                    s.handle_line("test-only")
                self.assertEqual(s._pending_village,key)
                self.assertIs(s.state, State.CHARGEN_CLASS)
                s.handle_line("ninjutsu")
                self.assertIs(s.state, State.CHARGEN_CLAN)
                s.handle_line(data_clans.clans_for_village(key)[0])
                self.assertIs(s.state, State.CHARGEN_LOADOUT)

    def test_override_code_and_cross_village_confirmation(self):
        content.populate()
        with patch.dict(os.environ, {"NINDO_VILLAGE_ACCESS_RAIN":"test-only-rain"}):
            self.assertTrue(village_access.verify_hidden_village_access_code("rain","test-only-rain"))
            self.assertFalse(village_access.verify_hidden_village_access_code("rain","wrong"))
            s, _ = self.session()
            s.handle_line("rain")
            s.handle_line("test-only-rain")
            s._pending_village="grass"
            s._pending_clan="uzumaki"
            s.state=State.CHARGEN_CONFIRM
            s.handle_line("yes")
            self.assertIs(s.state, State.CHARGEN_VILLAGE)
            self.assertIsNone(s.player)

    def test_retired_village_cannot_be_selected_even_with_access_code(self):
        content.populate()
        with patch.object(village_access, "verify_whirlpool_access_code", return_value=True):
            for alias in ("rock", "Ishigakure", "Ishi"):
                with self.subTest(alias=alias):
                    self.assertIsNone(data_villages.resolve_village_key(alias))
                    s, _ = self.session()
                    s.handle_line(alias)
                    self.assertIs(s.state, State.CHARGEN_VILLAGE)
                    self.assertIsNone(s._pending_village)
            self.assertFalse(village_access.verify_hidden_village_access_code("rock", "test-only"))
        self.assertEqual(data_villages.resolve_village_key("stone"), "stone")
        self.assertEqual(data_villages.resolve_village_key("moon"), "moon")
        self.assertEqual(data_villages.VILLAGES["moon"]["village_id"], 14)
        self.assertEqual(sum(not v.get("retired_at_creation") for v in data_villages.VILLAGES.values()), 13)
        self.assertIsNone(areas.find_area("rock"))
