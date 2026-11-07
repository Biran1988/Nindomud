"""Advanced Tracking scroll upgrades ordinary Track without a new command."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import areas
import combat
import commands
import data_jutsu
import tracking
import world
from models import Player
from session import Session, State


class AdvancedTrackingTests(unittest.TestCase):
    def setUp(self):
        self.rooms = {v: world.Room(v, f"Road {v}", "Crossing the border.")
                      for v in (997001, 997002, 997003, 997004)}
        for v in (997001, 997002, 997003):
            self.rooms[v].exits["north"] = v + 1
        for v in (997002, 997003, 997004):
            self.rooms[v].exits["south"] = v - 1
        self.area1 = NS(name="Leaf", vnum_start=997001, vnum_end=997002)
        self.area2 = NS(name="Road", vnum_start=997003, vnum_end=997004)
        self.fakeworld = NS(WORLD=NS(get=self.rooms.get))
        self.mob = NS(name="a highway rogue", room_vnum=997004,
                      instance_id=99881, health=100)
        self.sent = []
        self.actor = Session(self.sent.append, lambda: None)
        self.actor.state = State.PLAYING
        self.actor.account = NS(name="Tracker", staff_level="player")
        self.actor.player = Player("Tracker", "Tracker", village="leaf",
                                   primary_class="taijutsu", level=20,
                                   room_vnum=997001)
        self.actor.player.chakra = self.actor.player.maximum_chakra = 2000
        self.actor.player.stamina = self.actor.player.maximum_stamina = 2000
        self.actor.player.health = self.actor.player.maximum_health = 100
        self.actor.player.learned_skills = ["Advanced Tracking"]
        self.patchers = [
            patch.object(world.WORLD, "rooms", dict(self.rooms)),
            patch.object(combat, "MOBS_BY_ROOM", {997004: [self.mob]}),
            patch.object(areas, "find_area_for_vnum",
                         side_effect=lambda v: self.area1 if v <= 997002 else self.area2),
            patch.object(commands.jutsu_colors, "send", side_effect=lambda session, msg: session.send(msg)),
            patch.object(tracking.upkeep_reports if hasattr(tracking, "upkeep_reports") else
                         __import__("upkeep_reports"), "maintain_skill"),
        ]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)

    def test_upgrade_is_scroll_only_and_at_least_level_20(self):
        upgrade = data_jutsu.JUTSU["advanced tracking"]
        self.assertTrue(upgrade["scroll_only"])
        self.assertEqual(upgrade["level_requirement"], 20)
        self.assertNotIn("advanced tracking",
                         data_jutsu.jutsu_for_class_at_level("taijutsu", 20))
        self.assertTrue(tracking.has_advanced_tracking(self.actor.player))
        self.actor.player.level = 19
        self.assertFalse(tracking.has_advanced_tracking(self.actor.player))

    def test_shortest_route_crosses_areas_only_in_advanced_mode(self):
        self.assertIsNone(tracking.find_path(self.fakeworld, 997001, 997004, self.area2))
        self.assertEqual(tracking.find_path(self.fakeworld, 997001, 997004, None),
                         ["north", "north", "north"])
        self.rooms[997002].exit_flags["north"] = ["door"]
        self.rooms[997002].exit_door_open["north"] = False
        self.assertIsNone(tracking.find_path(self.fakeworld, 997001, 997004, None))

    def test_perform_track_at_20_uses_advanced_learned_scroll(self):
        p = self.actor.player
        with patch.object(tracking, "find_mob_anywhere_in_world", return_value=self.mob):
            commands.cmd_perform(self.actor, ["track", "highway", "rogue"])
        self.assertEqual(p.tracking_target_mob_id, self.mob.instance_id)
        self.assertIn("across country borders", "\n".join(self.sent))
        self.assertLess(p.chakra, 2000)

    def test_unlearned_or_underleveled_cannot_track(self):
        p = self.actor.player
        p.learned_skills = []
        with patch.object(tracking, "find_mob_anywhere_in_world", return_value=self.mob):
            commands.cmd_perform(self.actor, ["track", "highway", "rogue"])
        self.assertIsNone(p.tracking_target_mob_id)
        self.assertIn("must learn Track", "\n".join(self.sent))
        self.sent.clear()
        p.learned_skills = ["Advanced Tracking"]
        p.level = 19
        with patch.object(tracking, "find_mob_anywhere_in_world", return_value=self.mob):
            commands.cmd_perform(self.actor, ["track", "highway", "rogue"])
        self.assertIsNone(p.tracking_target_mob_id)

    def test_advanced_tracking_moves_through_area_boundary_each_pulse(self):
        self.actor.player.chakra = 2000
        tracking.start_tracking(self.actor.player, target_mob=self.mob,
                                area_name="Road")
        def move(session, direction):
            session.player.room_vnum = self.rooms[session.player.room_vnum].exits[direction]
        with patch.object(commands, "cmd_move", side_effect=move):
            for expected in (997002, 997003, 997004):
                tracking.tick_tracking(self.actor)
                self.assertEqual(self.actor.player.room_vnum, expected)
            tracking.tick_tracking(self.actor)
        self.assertIsNone(self.actor.player.tracking_target_mob_id)
        self.assertIn("caught up", "\n".join(self.sent))

    def test_normal_track_still_cannot_cross_area_boundary(self):
        p = self.actor.player
        p.level = 30
        p.learned_skills = ["Track"]
        tracking.start_tracking(p, target_mob=self.mob, area_name="Road")
        tracking.tick_tracking(self.actor)
        self.assertEqual(p.room_vnum, 997001)
        self.assertIsNone(p.tracking_target_mob_id)
        self.assertIn("no way to reach", "\n".join(self.sent))

    def test_scroll_read_grants_permanent_upgrade_at_20_only(self):
        p = self.actor.player
        p.inventory = ["Advanced Tracking Scroll"]
        p.learned_skills = []
        scroll = {"item_type": "scroll", "scroll_jutsu": "advanced tracking"}
        with patch.object(commands, "find_indexed_item", return_value="Advanced Tracking Scroll"), \
             patch.object(commands, "_find_object_prototype_by_name", return_value=scroll), \
             patch.object(commands.storage, "save_player") as saved:
            p.level = 19
            commands.cmd_read(self.actor, ["advanced", "tracking", "scroll"])
            self.assertIn("Advanced Tracking Scroll", p.inventory)
            self.assertNotIn("Advanced Tracking", p.learned_skills)
            p.level = 20
            commands.cmd_read(self.actor, ["advanced", "tracking", "scroll"])
            self.assertIn("Advanced Tracking", p.learned_skills)
            self.assertNotIn("Advanced Tracking Scroll", p.inventory)
            self.assertTrue(tracking.has_advanced_tracking(p))
            saved.assert_called()

    def test_advanced_is_not_a_separate_active_track_command(self):
        commands.cmd_perform(self.actor, ["advanced", "tracking", "target"])
        self.assertIn("Use 'perform track", "\n".join(self.sent))
        self.assertIsNone(self.actor.player.tracking_target_mob_id)


if __name__ == "__main__":
    unittest.main()
