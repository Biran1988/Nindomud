"""Iron Ascension has isolated rooms, 250 auto-balanced guards and durable rewards."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import combat
import iron_ascension as tower
import olc
import world
from models import Player


class IronAscensionTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("IronTester", "IronTester", level=250)
        self.player.room_vnum = tower.START
        self.lines = []
        self.session = SimpleNamespace(player=self.player, send=self.lines.append)
        self.world_patch = patch.object(world, "WORLD", world.World())
        self.mob_patch = patch.object(combat, "MOB_TEMPLATES", {})
        self.instances_patch = patch.object(combat, "MOBS_BY_ROOM", {})
        self.object_patch = patch.object(olc, "OBJECT_TEMPLATES", {})
        self.save_patch = patch("storage.save_player")
        for item in (self.world_patch, self.mob_patch, self.instances_patch,
                     self.object_patch, self.save_patch):
            item.start()

    def tearDown(self):
        for item in (self.save_patch, self.object_patch, self.instances_patch,
                     self.mob_patch, self.world_patch):
            item.stop()

    def test_full_tower_is_isolated_and_all_guards_auto_balance(self):
        with patch.object(tower, "_validate_area"), patch.object(
                combat, "spawn_mob", return_value=None) as spawner:
            tower.install()
        self.assertEqual(spawner.call_count, 250)
        self.assertEqual(len(world.WORLD.rooms), 250)
        self.assertEqual(len(combat.MOB_TEMPLATES), 250)
        first = world.WORLD.get(tower.START)
        last = world.WORLD.get(tower.START + 249)
        self.assertEqual(first.exits, {})
        self.assertEqual(last.exits, {})
        self.assertTrue(all(not room.exits for room in world.WORLD.rooms.values()))
        for floor in range(1, 251):
            template = combat.MOB_TEMPLATES[tower.guardian_vnum(floor)]
            self.assertTrue(template["auto_balance"])
            self.assertEqual(template["level"], floor)
        self.assertEqual(combat.MOB_TEMPLATES[tower.guardian_vnum(250)]["short_desc"], "the Iron Kage")
        heart = olc.OBJECT_TEMPLATES[tower.HEART_VNUM]
        self.assertEqual(heart["stat_bonuses"]["hitroll"], 25)
        self.assertEqual(heart["stat_bonuses"]["max_health"], 500)
        self.assertEqual(olc.OBJECT_TEMPLATES[tower.SCROLL_VNUM]["item_type"], "scroll")

    def test_kill_transfers_directly_without_progress_tracking(self):
        with patch.object(tower, "_validate_area"), patch.object(combat, "spawn_mob"):
            tower.install()
        guardian = SimpleNamespace(room_vnum=tower.START,
                                    template_vnum=tower.guardian_vnum(1))
        with patch("commands.cmd_look") as look:
            self.assertTrue(tower.defeated(self.session, guardian))
        self.assertEqual(self.player.room_vnum, tower.START + 1)
        self.assertFalse(hasattr(self.player, "iron_ascension_highest_floor"))
        self.assertEqual(world.WORLD.get(tower.START).exits, {})
        look.assert_called_once_with(self.session, [])

    def test_login_mid_tower_restarts_on_floor_one_without_checkpoint(self):
        with patch.object(tower, "_validate_area"), patch.object(combat, "spawn_mob"):
            tower.install()
            self.player.room_vnum = tower.START + 109
            self.assertTrue(tower.reset_run_on_login(self.session))
        self.assertEqual(self.player.room_vnum, tower.START)
        self.assertFalse(hasattr(self.player, "iron_ascension_highest_floor"))
        self.assertIn("floor 1", " ".join(self.lines))

    def test_final_guard_awards_once_and_scroll_teaches_passive(self):
        with patch.object(tower, "_validate_area"), patch.object(combat, "spawn_mob"):
            tower.install()
        self.player.room_vnum = tower.START + 249
        final = SimpleNamespace(room_vnum=self.player.room_vnum,
                                template_vnum=tower.guardian_vnum(250))
        with patch("session.ACTIVE_SESSIONS", []), patch("commands.cmd_look"):
            tower.defeated(self.session, final)
            self.assertEqual(self.player.room_vnum, tower.START)
            self.player.room_vnum = tower.START + 249
            tower.defeated(self.session, final)
        self.assertTrue(self.player.iron_ascension_completed)
        self.assertEqual(self.player.mission_points, 25)
        self.assertEqual(self.player.mission_points_earned_total, 25)
        self.assertFalse(hasattr(self.player, "iron_ascension_highest_floor"))
        self.assertIn(tower.HEART, self.player.inventory)
        self.assertIn(tower.SCROLL, self.player.inventory)
        self.assertTrue(tower.read_scroll(self.session, tower.SCROLL))
        self.assertIn(tower.SKILL, self.player.learned_skills)
        self.assertNotIn(tower.SCROLL, self.player.inventory)

    def test_iron_resolve_only_once_per_fight_and_heart_defense(self):
        mob = SimpleNamespace(instance_id=55)
        self.player.learned_skills.append(tower.SKILL)
        self.player.maximum_health = 100
        self.player.health = 25
        with patch.object(tower.time, "time", return_value=100.0):
            self.assertEqual(tower.reduce_incoming(self.session, mob, 10), 7)
            self.assertTrue(self.player._iron_resolve_fired)
            self.assertEqual(tower.reduce_incoming(self.session, mob, 10), 7)
        with patch.object(tower.time, "time", return_value=200.0):
            self.assertEqual(tower.reduce_incoming(self.session, mob, 10), 10)
        self.player.equipment["neck"] = tower.HEART
        with patch.object(tower.random, "randint", return_value=1):
            self.assertEqual(tower.reduce_incoming(self.session, mob, 100), 0)


if __name__ == "__main__":
    unittest.main()
