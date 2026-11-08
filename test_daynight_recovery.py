"""Regressions for the shinobi clock and road-only recovery items."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import combat
import commands
import door_links
import mainland_roads
import missions
import npc_schedules
import roadside_encounters
import roadside_item_missions as items
import storage
import weather
import world
from models import Player


class ShinobiClockTests(unittest.TestCase):
    def test_full_day_and_phase_are_absolute(self):
        self.assertEqual(weather.game_hour(0), 0)
        self.assertEqual(weather.game_hour(6 * 75), 6)
        self.assertEqual(weather.time_of_day(6 * 75), "day")
        self.assertEqual(weather.time_of_day(18 * 75), "night")
        self.assertEqual(weather.game_hour(24 * 75), 0)
        self.assertEqual(weather.formatted_time(13 * 75), "1:00 PM")

    def test_shop_hours_and_overnight_shifts(self):
        self.assertTrue(npc_schedules.within_hours(8, 20, 8))
        self.assertTrue(npc_schedules.within_hours(8, 20, 19))
        self.assertFalse(npc_schedules.within_hours(8, 20, 20))
        self.assertTrue(npc_schedules.within_hours(20, 6, 2))
        self.assertFalse(npc_schedules.within_hours(20, 6, 12))
        self.assertTrue(npc_schedules.within_hours(-1, -1, 12))

    def test_gate_states_mirror_and_reopen(self):
        original_world = world.WORLD
        fake = world.World()
        a, b = world.Room(90001, "Outside", ""), world.Room(90002, "Inside", "")
        fake.add_room(a)
        fake.add_room(b)
        fake.link(a.vnum, "north", b.vnum)
        a.exit_flags["north"] = ["door"]
        a.exit_door_open["north"] = True
        door_links.mirror(a, "north")
        proto = {99111: {
            "enabled": True, "gate_room_vnum": a.vnum, "gate_direction": "north",
            "gate_open_hour": 6, "gate_close_hour": 18,
        }}
        mobs = {a.vnum: [SimpleNamespace(template_vnum=99111, room_vnum=a.vnum)]}
        with patch.object(world, "WORLD", fake), \
                patch.object(combat, "MOB_TEMPLATES", proto), \
                patch.object(combat, "MOBS_BY_ROOM", mobs):
            self.assertEqual(npc_schedules.apply_all(hour=19), 1)
            self.assertFalse(a.exit_door_open["north"])
            self.assertFalse(b.exit_door_open["south"])
            self.assertTrue(npc_schedules.gate_scheduled_closed(b, "south", hour=19))
            self.assertEqual(npc_schedules.apply_all(hour=8), 1)
            self.assertTrue(a.exit_door_open["north"])
            self.assertTrue(b.exit_door_open["south"])


class RoadsideRecoveryTests(unittest.TestCase):
    def setUp(self):
        items._ITEMS.clear()
        self.addCleanup(items._ITEMS.clear)

    def test_main_villages_never_qualify_but_inns_do(self):
        roads, _ = mainland_roads.build_rooms()
        _, _, _, _, details = roadside_encounters.build_plan()
        chosen_road = next(iter(roads.values()))
        chosen_inn = next(iter(details["inns"].values()))
        inn_vnum = chosen_inn["porch"]
        inn = world.Room(inn_vnum, chosen_inn["name"] + " - Roadside Courtyard", "")
        village = world.Room(1, "Hidden Leaf Village", "")
        # Reused road VNUMs are excluded if their name has been changed.
        replaced = world.Room(chosen_road.vnum + 1, "Private Builder's Residence", "")
        fake = SimpleNamespace(get={room.vnum: room for room in
                                  (chosen_road, inn, village, replaced)}.get)
        with patch.object(world, "WORLD", fake):
            found = items.eligible_rooms()
        self.assertIn(chosen_road.vnum, found)
        self.assertIn(inn_vnum, found)
        self.assertNotIn(village.vnum, found)
        self.assertNotIn(replaced.vnum, found)

    def test_one_road_item_can_be_claimed_only_by_assigned_ninja(self):
        player = Player("NarutoTest", "test", village="leaf", level=50)
        player.room_vnum = 20501
        fake_room = world.Room(20501, "Eastern Pilgrim Road", "")
        fake_world = SimpleNamespace(get=lambda vnum: fake_room if vnum == 20501 else None)
        choices = [20501]
        with patch.object(items, "eligible_rooms", return_value=choices), \
                patch.object(world, "WORLD", fake_world), \
                patch.object(items.time, "time", return_value=1000):
            result = missions.request_item_mission(player, "c")
        self.assertIn("Mission requested", result)
        self.assertEqual(len(player.active_missions), 1)
        mission = player.active_missions[0]["dynamic"]
        self.assertEqual(mission["mission_type"], "retrieve")
        self.assertEqual(mission["quest_room_vnum"], 20501)
        self.assertEqual(items.visible_items(20501), [mission["quest_item_name"]])
        self.assertEqual(fake_room.ground_items, [])  # no persisted world pollution

        stranger = Player("Stranger", "stranger", village="leaf", level=50)
        stranger.room_vnum = 20501
        denied = []
        session_other = SimpleNamespace(player=stranger, send=denied.append)
        self.assertTrue(items.try_pickup(session_other, mission["quest_item_name"]))
        self.assertIn("another ninja", denied[0])
        self.assertEqual(len(player.active_missions), 1)

        received = []
        session = SimpleNamespace(player=player, send=received.append)
        def finish(who, quest, entry):
            who.active_missions.remove(entry)
            who.completed_missions.append(quest["mission_id"])
            return ["Mission complete."]
        with patch.object(missions, "_complete_mission", side_effect=finish), \
                patch.object(storage, "save_player") as save, \
                patch.object(items.time, "time", return_value=1005):
            self.assertTrue(items.try_pickup(session, mission["quest_item_name"]))
        self.assertEqual(player.active_missions, [])
        self.assertEqual(items.visible_items(20501), [])
        self.assertIn("Mission complete.", received)
        save.assert_called()

    def test_expiring_item_mission_cleans_up_without_rewards(self):
        player = Player("Tester", "tester", village="leaf", level=50)
        player.room_vnum = 20501
        fake_world = SimpleNamespace(get=lambda _vnum: world.Room(20501, "Road", ""))
        with patch.object(items, "eligible_rooms", return_value=[20501]), \
                patch.object(world, "WORLD", fake_world), \
                patch.object(items.time, "time", return_value=1000):
            missions.request_item_mission(player, "c")
        self.assertEqual(len(items.visible_items(20501)), 1)
        old_rewards = (player.ryo, player.mission_points)
        self.assertEqual(len(missions.expire_missions(player, now=2800)), 1)
        self.assertEqual(items.visible_items(20501), [])
        self.assertEqual((player.ryo, player.mission_points), old_rewards)


if __name__ == "__main__":
    unittest.main()
