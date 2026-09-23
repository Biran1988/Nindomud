import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import colors
import combat
import damage_messages
import leveling
import olc
import spawn_points
import storage
import world
import world_persistence
from models import Player


class DamageMessageTests(unittest.TestCase):
    def test_full_scale_is_colored_and_number_free(self):
        expected = {
            1: "TRIVIAL",
            599: "DEVASTATING",
            900: "OBLITERATING",
            9999: "REALITY-SHATTERING",
            10000: "EXTINCTION-LEVEL",
            50000: "EXTINCTION-LEVEL",
        }
        for amount, label in expected.items():
            text = damage_messages.describe_damage(amount)
            self.assertRegex(text, r"^&\[\d{1,3}\].+&x$")
            self.assertEqual(colors.render(text, False), label)
            self.assertNotIn(str(amount), colors.render(text, False))

    def test_every_tier_uses_a_real_xterm_color(self):
        colors_used = [color for _maximum, _label, color in damage_messages.DAMAGE_TIERS]
        self.assertEqual(len(colors_used), len(set(colors_used)))
        self.assertTrue(all(0 <= color <= 255 for color in colors_used))


class ProgressiveExperienceTests(unittest.TestCase):
    def test_cumulative_cubic_curve(self):
        self.assertEqual(leveling.cumulative_xp_for_level(1), 0)
        self.assertEqual(leveling.cumulative_xp_for_level(2), 1_000)
        self.assertEqual(leveling.cumulative_xp_for_level(3), 8_000)
        self.assertEqual(leveling.cumulative_xp_for_level(100), 970_299_000)
        self.assertEqual(leveling.xp_for_next_level(2), 8_000)

    def test_mob_reward_slides_by_each_players_level(self):
        base = leveling.mob_base_experience(20)
        self.assertEqual(leveling.mob_kill_experience(20, 20), base)
        self.assertEqual(leveling.mob_kill_experience(30, 20), 0)
        self.assertEqual(leveling.mob_kill_experience(10, 20), round(base * 1.30))
        self.assertGreater(leveling.mob_kill_experience(19, 20), base)
        self.assertLess(leveling.mob_kill_experience(21, 20), base)

    def test_legacy_migration_preserves_level_progress(self):
        player = Player("Legacy", "Legacy", level=10, experience=9_500)
        player.experience_curve_version = 1
        self.assertTrue(leveling.migrate_experience_curve(player))
        floor = leveling.cumulative_xp_for_level(10)
        self.assertEqual(player.experience, floor + round(leveling.xp_band_for_level(10) * 0.5))
        self.assertEqual(player.level, 10)
        self.assertFalse(leveling.migrate_experience_curve(player))


class BuilderPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patches = [
            patch.object(storage, "DATA_DIR", self.temp.name),
            patch.object(combat, "MOB_TEMPLATES", {}),
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(olc, "OBJECT_TEMPLATES", {}),
            patch.object(world.WORLD, "rooms", {}),
            patch.object(olc, "_log"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        world.WORLD.add_room(world.Room(9000, "Test Room", "A test room."))

    def test_save_world_refreshes_shop_and_item_spawn_templates(self):
        combat.MOB_TEMPLATES[9100] = combat.default_template(9100, "shopkeeper")
        combat.MOB_TEMPLATES[9100]["shopkeeper"] = True
        olc.OBJECT_TEMPLATES[9200] = olc.default_object(9200, "training kunai")
        self.assertEqual(spawn_points.add_spawn_point("mob", 9100, 9000), "")
        self.assertEqual(spawn_points.add_spawn_point("item", 9200, 9000), "")

        combat.MOB_TEMPLATES[9100]["shop_items"] = [9200]
        olc.OBJECT_TEMPLATES[9200]["cost"] = 777
        world_persistence.save_world()

        combat.MOB_TEMPLATES.clear()
        olc.OBJECT_TEMPLATES.clear()
        spawn_points.restore_custom_templates()
        self.assertEqual(combat.MOB_TEMPLATES[9100]["shop_items"], [9200])
        self.assertEqual(olc.OBJECT_TEMPLATES[9200]["cost"], 777)

    def test_smaug_builder_convenience_commands(self):
        session = SimpleNamespace(
            account=SimpleNamespace(staff_level="builder"),
            player=SimpleNamespace(name="Builder", room_vnum=9000),
            send=Mock(),
        )
        olc.cmd_mcreate(session, ["9101", "academy", "student"])
        olc.cmd_ocreate(session, ["9201", "wooden", "kunai"])
        olc.cmd_minvoke(session, ["9101"])
        olc.cmd_oinvoke(session, ["9201"])
        self.assertIn(9101, combat.MOB_TEMPLATES)
        self.assertEqual(len(combat.mobs_in_room(9000)), 1)
        self.assertIn("wooden kunai", world.WORLD.get(9000).ground_items)

    def test_ostat_unique_name_and_ambiguity(self):
        session = SimpleNamespace(
            account=SimpleNamespace(staff_level="builder"),
            player=SimpleNamespace(name="Builder", room_vnum=9000),
            send=Mock(),
        )
        olc.OBJECT_TEMPLATES[9201] = olc.default_object(9201, "academy kunai")
        olc.cmd_ostat(session, ["academy"])
        self.assertIn("Object: [9201]", session.send.call_args.args[0])
        olc.OBJECT_TEMPLATES[9202] = olc.default_object(9202, "academy sword")
        olc.cmd_ostat(session, ["academy"])
        self.assertIn("ambiguous", session.send.call_args.args[0])
        self.assertIn("9201", session.send.call_args.args[0])
        self.assertIn("9202", session.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
