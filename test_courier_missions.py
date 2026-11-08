"""Courier delivery: items, actual NPC recipients, rewards and anti-trade safety."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import combat
import commands
import courier_missions
import missions
from models import Player


class CourierMissionsTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Courier", "Courier", primary_class="taijutsu", level=60)
        self.player.village = "leaf"
        self.player.room_vnum = 201
        self.player.inventory.clear()
        self.sent = []
        self.session = SimpleNamespace(
            player=self.player, send=self.sent.append,
            active_sessions=lambda: [],
        )
        self.mob = SimpleNamespace(template_vnum=6005, name="a Leaf villager",
                                   health=100, room_vnum=201)
        self.room = SimpleNamespace(name="Leaf Village Garden")
        self.recipient_patch = patch.object(courier_missions, "_recipients",
                                            return_value=[(self.mob, 201, self.room, "leaf")])
        self.recipient_patch.start()
        self.save = patch("storage.save_player")
        self.save.start()

    def tearDown(self):
        self.save.stop()
        self.recipient_patch.stop()

    def accept(self, rank="d"):
        result = missions.request_courier_mission(self.player, rank)
        self.assertTrue(result.startswith("Mission requested:"), result)
        entry = self.player.active_missions[-1]
        return entry, entry["dynamic"]

    def test_request_gives_mission_bound_inventory_item(self):
        entry, mission = self.accept()
        self.assertEqual(mission["mission_type"], "courier")
        self.assertIn(mission["quest_item_name"], self.player.inventory)
        self.assertTrue(courier_missions.is_parcel(mission["quest_item_name"]))
        self.assertEqual(entry["progress"], 0)
        self.assertEqual(mission["delivery_mob_template"], 6005)
        self.assertIn("DELIVER", missions.mission_info(self.player).upper())
        self.assertEqual(mission["rank"], "D-Rank")

    def test_correct_npc_finishes_and_pays_once(self):
        entry, mission = self.accept()
        with patch.object(combat, "mobs_in_room", return_value=[self.mob]):
            self.assertTrue(courier_missions.try_deliver(self.session))
        self.assertNotIn(entry, self.player.active_missions)
        self.assertNotIn(mission["quest_item_name"], self.player.inventory)
        self.assertIn(mission["mission_id"], self.player.completed_missions)
        completed = list(self.player.completed_missions)
        self.assertFalse(courier_missions.try_deliver(self.session))
        self.assertEqual(self.player.completed_missions, completed)

    def test_wrong_npc_or_room_cannot_claim_parcel(self):
        entry, mission = self.accept()
        with patch.object(combat, "mobs_in_room", return_value=[self.mob]):
            self.assertTrue(courier_missions.try_deliver(self.session, "wrong name"))
        self.assertIn(entry, self.player.active_missions)
        self.assertIn(mission["quest_item_name"], self.player.inventory)
        self.player.room_vnum = 202
        with patch.object(combat, "mobs_in_room", return_value=[self.mob]):
            self.assertTrue(courier_missions.try_deliver(self.session))
        self.assertIn(entry, self.player.active_missions)

    def test_failure_and_expiry_remove_only_own_cargo(self):
        first, first_mission = self.accept()
        second, second_mission = self.accept("c")
        self.assertIn(first_mission["quest_item_name"], self.player.inventory)
        self.assertIn(second_mission["quest_item_name"], self.player.inventory)
        missions.fail_mission(self.player, first_mission["mission_id"])
        self.assertNotIn(first_mission["quest_item_name"], self.player.inventory)
        self.assertIn(second_mission["quest_item_name"], self.player.inventory)
        missions.expire_missions(self.player, now=second["expires_at"] + 1)
        self.assertNotIn(second_mission["quest_item_name"], self.player.inventory)

    def test_parcel_is_not_drop_or_tradeable(self):
        _, mission = self.accept()
        commands.cmd_drop(self.session, ["parcel"])
        self.assertIn(mission["quest_item_name"], self.player.inventory)
        self.assertTrue(any("cannot be dropped" in line for line in self.sent))

    def test_mission_command_requests_delivery_and_saves(self):
        commands.cmd_mission(self.session, ["request", "delivery", "b"])
        self.assertTrue(any("Mission requested:" in line for line in self.sent))
        self.assertEqual(self.player.active_missions[-1]["dynamic"]["rank"], "B-Rank")


if __name__ == "__main__":
    unittest.main()
