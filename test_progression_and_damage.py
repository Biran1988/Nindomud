import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import colors
import combat
import commands
import content
import damage_messages
import legendary_items
import leveling
import olc
import playershops
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

    def test_shopkeeper_uses_current_item_vnum_for_list_and_purchase(self):
        template = combat.default_template(9100, "shopkeeper")
        template.update(shopkeeper=True, shop_items=[9200])
        combat.MOB_TEMPLATES[9100] = template
        olc.OBJECT_TEMPLATES[9200] = olc.default_object(9200, "old kunai")
        shopkeeper = combat.spawn_mob(9100, 9000)
        player = Player("Buyer", "Buyer")
        player.room_vnum = 9000
        player.ryo = 100
        session = SimpleNamespace(player=player, send=Mock())
        builder = SimpleNamespace(account=SimpleNamespace(staff_level="builder"),
                                  player=SimpleNamespace(name="Builder", room_vnum=9000), send=Mock())
        olc.cmd_oset(builder, ["9200", "short", "new", "kunai"])
        olc.cmd_oset(builder, ["9200", "cost", "30"])
        olc.cmd_oset(builder, ["9200", "weapontype", "kunai"])
        olc.cmd_oset(builder, ["9200", "damage", "11"])
        olc.cmd_oset(builder, ["9200", "level", "5"])
        player.level = 4
        self.assertIn(9200, combat.mob_shop_items(shopkeeper))
        commands.cmd_list(session, [])
        shown = colors.render(session.send.call_args.args[0], False)
        self.assertIn("new kunai - 30 ryo (level 5)", shown)
        self.assertNotIn("old kunai", shown)
        with patch.object(commands, "_fire_item_trigger"):
            commands.cmd_buy(session, ["new", "kunai"])
            self.assertIn("level 5", session.send.call_args.args[0])
            self.assertEqual((player.ryo, player.inventory), (100, []))
            player.level = 5
            commands.cmd_buy(session, ["new", "kunai"])
        self.assertIn("new kunai", player.inventory)
        self.assertEqual(player.ryo, 70)
        player.equipment["wielded"] = player.inventory.pop()
        self.assertEqual(commands.equipped_weapon_type_damage_bonus(player), 11)

    def test_player_shop_stock_tracks_prototype_vnum_after_rename(self):
        olc.OBJECT_TEMPLATES[9200] = olc.default_object(9200, "old kunai")
        olc.OBJECT_TEMPLATES[9200]["level"] = 5
        owner = Player("Owner", "Owner")
        owner.shop_stock = [{"item_name": "old kunai", "price": 20,
                             "item_vnum": playershops.item_vnum_for_stock("old kunai")},
                            {"item_name": "old kunai", "price": 20}]
        shopkeeper = SimpleNamespace(player_shop_owner="Owner", name="shopkeeper")
        builder = SimpleNamespace(account=SimpleNamespace(staff_level="builder"),
                                  player=SimpleNamespace(name="Builder"), send=Mock())
        olc.cmd_oset(builder, ["9200", "short", "new", "kunai"])
        buyer = Player("Buyer", "Buyer")
        buyer.ryo = 50
        buyer.level = 4
        with patch.object(playershops, "_find_owner_player", return_value=(owner, True)):
            self.assertEqual([row["item_name"] for row in playershops.stock_for_display(shopkeeper)],
                             ["new kunai", "new kunai"])
            ok, message, _ = playershops.buy_from_shop(shopkeeper, buyer, "new kunai")
            self.assertFalse(ok)
            self.assertIn("level 5", message)
            self.assertEqual((buyer.ryo, buyer.inventory, len(owner.shop_stock)), (50, [], 2))
            buyer.level = 5
            ok, item, price = playershops.buy_from_shop(shopkeeper, buyer, "new kunai")
            self.assertEqual(playershops.stock_for_display(shopkeeper)[0]["item_name"], "new kunai")
        self.assertTrue(ok)
        self.assertEqual((item, price, buyer.ryo), ("new kunai", 20, 30))
        self.assertEqual(buyer.inventory, ["new kunai"])
        self.assertEqual(len(owner.shop_stock), 1)

    def test_static_shop_uses_registered_item_level(self):
        olc.OBJECT_TEMPLATES[9200] = olc.default_object(9200, "training kunai")
        olc.OBJECT_TEMPLATES[9200]["level"] = 8
        player = Player("Buyer", "Buyer")
        player.room_vnum = 9000
        player.ryo = 50
        player.level = 7
        session = SimpleNamespace(player=player, send=Mock())
        with patch.object(content, "SHOPS", {9000: {"type": "weapons", "items": [
                {"name": "training kunai", "price": 20}]}}), \
             patch.object(commands, "_fire_item_trigger"):
            commands.cmd_buy(session, ["training", "kunai"])
            self.assertIn("level 8", session.send.call_args.args[0])
            self.assertEqual((player.ryo, player.inventory), (50, []))
            player.level = 8
            commands.cmd_buy(session, ["training", "kunai"])
        self.assertEqual((player.ryo, player.inventory), (30, ["training kunai"]))

    def test_kage_shop_uses_current_prototype_name_and_level(self):
        olc.OBJECT_TEMPLATES[9200] = olc.default_object(9200, "new legendary kunai")
        olc.OBJECT_TEMPLATES[9200]["level"] = 10
        player = Player("Buyer", "Buyer")
        player.mission_points = 20
        player.level = 9
        player.village = "leaf"
        session = SimpleNamespace(player=player, send=Mock())
        data = {"vnum": 9200, "short_desc": "old legendary kunai", "cost_mission_points": 15}
        with patch.object(commands, "_own_kage_chamber", return_value=True), \
             patch.object(legendary_items, "LEGENDARY_ITEMS", {"old legendary kunai": data}):
            commands.cmd_list(session, [])
            self.assertIn("new legendary kunai", colors.render(session.send.call_args.args[0], False))
            commands.cmd_buy(session, ["new", "legendary", "kunai"])
            self.assertIn("level 10", session.send.call_args.args[0])
            self.assertEqual((player.mission_points, player.inventory), (20, []))
            player.level = 10
            commands.cmd_buy(session, ["new", "legendary", "kunai"])
        self.assertEqual((player.mission_points, player.inventory), (5, ["new legendary kunai"]))

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
