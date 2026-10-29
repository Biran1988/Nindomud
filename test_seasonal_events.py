"""Calendar, seasonal spawns, loot, and annual gifts."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path

import combat
import commands
import content
import seasonal_events as events
import storage
import world_persistence
from models import Player


class Session:
    def __init__(self, name="Tester"):
        self.player = Player(name, name)
        self.messages = []

    def send(self, message):
        self.messages.append(message)

    def broadcast_room(self, message, exclude_self=False):
        self.messages.append(message)


class SeasonalTests(unittest.TestCase):
    def test_july_fourth_gifts_are_once_per_year_and_items_work(self):
        self.assertTrue(events.july_fourth_active(date(2026, 7, 4)))
        self.assertFalse(events.july_fourth_active(date(2026, 7, 5)))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")), \
                 patch.object(combat, "MOBS_BY_ROOM", {}), \
                 patch.object(combat, "MOB_TEMPLATES", {}):
                events.sync_uncle_sam(date(2026, 7, 4))
                for room in events.kage_rooms():
                    self.assertEqual(len(combat.mobs_in_room(room)), 1)
                self.assertTrue(combat.is_immortal_mob(combat.mobs_in_room(events.hokage_room())[0]))
                self.assertNotIn(str(events.UNCLE_SAM_VNUM), world_persistence.snapshot_world()["mobs"])
                session = Session()
                session.player.room_vnum = events.hokage_room()
                session.player.health = session.player.chakra = session.player.stamina = 5
                self.assertTrue(events.claim_july_fourth(session, date(2026, 7, 4)))
                self.assertTrue(events.claim_july_fourth(session, date(2026, 7, 4)))
                self.assertEqual(len(session.player.inventory), 3)
                self.assertEqual(storage.load_player("Tester").last_july_fourth_gift_year, 2026)
                second = Session("Second")
                second.player.room_vnum = content._VILLAGE_ROOMS["sand"]["kage"]
                self.assertTrue(events.claim_july_fourth(second, date(2026, 7, 4)))
                self.assertEqual(len(second.player.inventory), 3)
                self.assertTrue(events.use_fireworks(session, "fireworks"))
                self.assertTrue(events.eat_july_fourth_food(session, "popsicle"))
                self.assertTrue(events.eat_july_fourth_food(session, "bbq"))
                self.assertEqual((session.player.health, session.player.chakra, session.player.stamina), (100, 65, 100))
                events.sync_uncle_sam(date(2026, 7, 5))
                for room in events.kage_rooms():
                    self.assertFalse(combat.mobs_in_room(room))

    def test_thanksgiving_turkeys_are_capped_and_respawn_after_delay(self):
        self.assertTrue(events.thanksgiving_active(date(2026, 11, 26)))
        self.assertTrue(events.thanksgiving_active(date(2026, 11, 29)))
        self.assertFalse(events.thanksgiving_active(date(2026, 11, 30)))
        with patch.object(combat, "MOBS_BY_ROOM", {}), \
             patch.object(combat, "MOB_TEMPLATES", {}), \
             patch.object(events, "_area_rooms", return_value={"leaf": [101, 102], "stone": [201]}), \
             patch.object(events.random, "choice", side_effect=lambda rooms: rooms[0]), \
             patch("areas.find_area_for_vnum", return_value=SimpleNamespace(name="leaf")):
            events._turkey_cooldowns.clear()
            day = date(2026, 11, 26)
            events.sync_turkeys(day, now=1000)
            events.sync_turkeys(day, now=1001)
            self.assertEqual(len(combat.mobs_in_room(101)), 2)
            self.assertEqual(len(combat.mobs_in_room(201)), 2)
            turkey = combat.mobs_in_room(101)[0]
            self.assertLessEqual(turkey.level, combat.MAX_KILLABLE_EVENT_MOB_LEVEL)
            self.assertTrue(combat.MOB_TEMPLATES[events.TURKEY_VNUM][combat.EVENT_KILLABLE_TAG])
            self.assertEqual(turkey.loot_items, [events.TURKEY_MEAL, events.TURKEY_FEATHER, events.TURKEY_FEATHER])
            events.turkey_defeated(turkey, now=1000)
            combat.remove_mob(turkey)
            events.sync_turkeys(day, now=1001)
            self.assertEqual(len(combat.mobs_in_room(101)), 1)
            events.sync_turkeys(day, now=1000 + events.TURKEY_RESPAWN_SECONDS)
            self.assertEqual(len(combat.mobs_in_room(101)), 2)
            events.sync_turkeys(date(2026, 11, 30), now=2000)
            self.assertFalse(any(m.template_vnum == events.TURKEY_VNUM for mobs in combat.MOBS_BY_ROOM.values() for m in mobs))

    def test_turkey_food_and_feather_sale(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")):
                session = Session()
                session.player.health = session.player.chakra = session.player.stamina = 5
                session.player.inventory = [events.TURKEY_MEAL, events.TURKEY_FEATHER]
                self.assertTrue(events.eat_turkey(session, "turkey"))
                self.assertEqual((session.player.health, session.player.chakra, session.player.stamina), (100, 75, 100))
                with patch.object(commands, "_find_shopkeeper", return_value=SimpleNamespace(name="merchant")), \
                     patch.object(combat, "mob_shop_buys_categories", return_value=["weapon"]):
                    commands.cmd_sell(session, ["feather"])
                self.assertEqual(session.player.ryo, 500)
                self.assertNotIn(events.TURKEY_FEATHER, session.player.inventory)

    def test_holiday_weeks_and_egg_from_each_ordinary_kill(self):
        self.assertEqual(events.easter_sunday(2026), date(2026, 4, 5))
        self.assertTrue(events.easter_active(date(2026, 3, 30)))
        self.assertTrue(events.easter_active(date(2026, 4, 5)))
        self.assertFalse(events.easter_active(date(2026, 4, 6)))
        self.assertTrue(events.christmas_active(date(2026, 12, 24)))
        self.assertFalse(events.christmas_active(date(2027, 1, 1)))
        mob = SimpleNamespace(loot_items=["Kunai"], tailed_beast_key=None)
        with patch.object(combat, "is_shadow_clone", return_value=False):
            self.assertEqual(events.mob_loot(mob, date(2026, 4, 5)), ["Kunai", events.EGG])
            self.assertEqual(events.mob_loot(mob, date(2026, 4, 6)), ["Kunai"])

    def test_santa_each_kage_and_one_persistent_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")), \
                 patch.object(combat, "MOBS_BY_ROOM", {}), \
                 patch.object(combat, "MOB_TEMPLATES", {}):
                events.sync_visitors(date(2026, 12, 25))
                for room in events.kage_rooms():
                    self.assertEqual(sum(m.template_vnum == events.SANTA_VNUM for m in combat.mobs_in_room(room)), 1)
                events.sync_visitors(date(2026, 12, 25))
                self.assertNotIn(str(events.SANTA_VNUM), world_persistence.snapshot_world()["mobs"])
                session = Session()
                session.player.room_vnum = content._VILLAGE_ROOMS["leaf"]["kage"]
                self.assertTrue(events.claim_present(session, date(2026, 12, 25)))
                self.assertTrue(events.claim_present(session, date(2026, 12, 25)))
                self.assertEqual(session.player.inventory.count(events.PRESENT), 1)
                self.assertEqual(storage.load_player("Tester").last_christmas_present_year, 2026)
                events.sync_visitors(date(2027, 1, 1))
                self.assertFalse(any(m.template_vnum == events.SANTA_VNUM for mobs in combat.MOBS_BY_ROOM.values() for m in mobs))

    def test_open_and_use_candy_after_season(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp), \
                 patch.object(storage, "ACCOUNTS_DIR", str(Path(tmp) / "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", str(Path(tmp) / "players")), \
                 patch.object(events.random, "choice", return_value="A Spring Chocolate"):
                session = Session()
                session.player.health = 10
                session.player.inventory.append(events.EGG)
                self.assertTrue(events.use_holiday_item(session, "egg"))
                self.assertIn("A Spring Chocolate", session.player.inventory)
                self.assertTrue(events.use_holiday_item(session, "chocolate"))
                self.assertEqual(session.player.health, 70)
                self.assertGreater(session.player.holiday_xp_boost_until, 0)


if __name__ == "__main__":
    unittest.main()
