"""Halloween week, temporary 20-room zone, vendors, mobs, boss and candy."""
import unittest
from datetime import date, timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import halloween_event as event
import olc
import seasonal_events
import session as session_module
import world
import world_persistence
from models import Player


class HalloweenEventTests(unittest.TestCase):
    def setUp(self):
        self.w = world.World()
        self.w.add_room(world.Room(999, "Home", "A quiet village room.", safe=True))
        self.mob_templates = {}
        self.mob_rooms = {}
        self.item_templates = {}
        self.owners = {}
        self.deaths = {}
        self.patches = [
            patch.object(world, "WORLD", self.w),
            patch.object(commands, "WORLD", self.w),
            patch.object(combat, "MOB_TEMPLATES", self.mob_templates),
            patch.object(combat, "MOBS_BY_ROOM", self.mob_rooms),
            patch.object(olc, "OBJECT_TEMPLATES", self.item_templates),
            patch.object(event, "_owned_rooms", self.owners),
            patch.object(event, "_deaths", self.deaths),
            patch.object(session_module, "ACTIVE_SESSIONS", []),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.player = Player("HalloweenTester", "HalloweenTester", level=100,
                             village="leaf", clan="nara", primary_class="taijutsu")
        self.player.room_vnum = 999
        self.player.ryo = 100_000
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          send=Mock(), combat_target=None, pvp_target=None)
        self.halloween_date = date(2026, 10, 31)

    def build(self):
        event.sync(self.halloween_date)

    def test_halloween_week_monday_to_sunday(self):
        self.assertEqual(event.week_bounds(2026), (date(2026, 10, 26), date(2026, 11, 1)))
        for d in (date(2026, 10, 26), self.halloween_date, date(2026, 11, 1)):
            self.assertTrue(event.active(d))
        for d in (date(2026, 10, 25), date(2026, 11, 2), date(2027, 9, 30)):
            self.assertFalse(event.active(d))

    def test_20_connected_rooms_and_actual_undead_boss_vendors(self):
        self.build()
        self.assertEqual(len(self.owners), 20)
        seen = {event.ROOM_START}
        frontier = [event.ROOM_START]
        while frontier:
            for nxt in self.w.get(frontier.pop()).exits.values():
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        self.assertEqual(seen, set(event.ROOM_VNUMS))
        self.assertEqual([m.template_vnum for m in combat.mobs_in_room(100019)], [event.BOSS_VNUM])
        self.assertEqual([m.template_vnum for m in combat.mobs_in_room(100002)], [event.COSTUME_MERCHANT])
        self.assertEqual([m.template_vnum for m in combat.mobs_in_room(100003)], [event.CANDY_MERCHANT])
        self.assertTrue(combat.is_shopkeeper(combat.mobs_in_room(100002)[0]))
        self.assertEqual(len(combat.mob_shop_items(combat.mobs_in_room(100002)[0])), 5)

    def test_all_killable_halloween_mobs_including_boss_are_level_50_or_less(self):
        self.build()
        self.assertEqual(event.MOB_SPAWNS[-1][2], combat.MAX_KILLABLE_EVENT_MOB_LEVEL)
        for room_index, vnum, configured_level, *_ in event.MOB_SPAWNS:
            template = self.mob_templates[vnum]
            self.assertLessEqual(configured_level, combat.MAX_KILLABLE_EVENT_MOB_LEVEL)
            self.assertLessEqual(template["level"], combat.MAX_KILLABLE_EVENT_MOB_LEVEL)
            self.assertTrue(template[combat.EVENT_KILLABLE_TAG])
            spawned = next(mob for mob in combat.mobs_in_room(event.ROOM_START + room_index)
                           if mob.template_vnum == vnum)
            self.assertEqual(spawned.level, configured_level)

        boss = combat.mobs_in_room(event.ROOM_START + 19)[0]
        self.assertEqual(boss.max_health, 9500)  # Boss difficulty is preserved.
        for vnum in (event.COSTUME_MERCHANT, event.CANDY_MERCHANT, event.TRICK_NPC):
            self.assertFalse(self.mob_templates[vnum][combat.EVENT_KILLABLE_TAG])

    def test_event_spawn_level_cap_protects_against_high_template_level(self):
        self.build()
        vnum = event.BOSS_VNUM
        self.mob_templates[vnum]["level"] = 100
        extra_boss = combat.spawn_mob(vnum, event.ROOM_START + 19)
        self.assertEqual(extra_boss.level, combat.MAX_KILLABLE_EVENT_MOB_LEVEL)
        # Other world mobs are deliberately not subject to this seasonal cap.
        normal = combat.default_template(999991, "a non-event guardian")
        normal["level"] = 90
        self.mob_templates[999991] = normal
        other = combat.spawn_mob(999991, 999)
        self.assertEqual(other.level, 90)

    def test_no_builder_collision_or_snapshot_pollution(self):
        self.w.add_room(world.Room(100010, "Custom Area", "Saved builder area."))
        self.build()
        self.assertIsNone(self.w.get(100000))
        self.assertEqual(self.w.get(100010).name, "Custom Area")
        self.assertEqual(self.owners, {})
        del self.w.rooms[100010]
        self.build()
        snap = world_persistence.snapshot_world()
        self.assertEqual(set(snap["rooms"]), {"999"})
        self.assertEqual(snap["mobs"], {})
        self.assertEqual(snap["items"], {})
        # Existing builder vnums always survive shutdown.
        self.w.add_room(world.Room(100030, "Builder's Fort", "Permanent."))
        event.sync(date(2026, 11, 2))
        self.assertEqual(self.w.get(100030).name, "Builder's Fort")
        self.assertIsNone(self.w.get(100000))
        self.assertIn(event.MASK_VNUM, self.item_templates)  # earned mask continues to work

    def test_teleport_entrance_return_and_combat_restrictions(self):
        with patch.object(event, "active", return_value=False):
            event.command_teleport(self.session, ["halloween"])
        self.assertEqual(self.player.room_vnum, 999)
        self.build()
        with (patch.object(event, "active", return_value=True),
              patch("storage.save_player"),
              patch.object(commands, "cmd_look"),
              patch.object(commands, "_fire_enter_triggers")):
            event.command_teleport(self.session, ["halloween"])
            self.assertEqual(self.player.room_vnum, 100000)
            self.assertEqual(self.player.halloween_return_vnum, 999)
            self.session.combat_target = NS()
            event.command_teleport(self.session, ["return"])
            self.assertEqual(self.player.room_vnum, 100000)
            self.session.combat_target = None
            event.command_teleport(self.session, ["return"])
        self.assertEqual(self.player.room_vnum, 999)
        self.assertEqual(self.player.halloween_return_vnum, 0)

    def test_vendor_purchase_and_costume_stats(self):
        self.build()
        self.player.room_vnum = 100002
        commands.cmd_list(self.session, [])
        self.assertIn("Witchlight Robe", self.session.send.call_args.args[0])
        commands.cmd_buy(self.session, ["witchlight", "robe"])
        self.assertIn("A Witchlight Robe", self.player.inventory)
        self.assertEqual(self.player.ryo, 100_000 - 2600)
        before = self.player.maximum_chakra
        intel = self.player.intelligence
        with patch.object(commands, "_fire_item_trigger"):
            commands.cmd_wear(self.session, ["witchlight", "robe"])
        self.assertEqual(self.player.maximum_chakra, before + 55)
        self.assertEqual(self.player.intelligence, intel + 2)

    def test_global_candy_and_rare_mask_are_real_corpse_loot(self):
        self.build()
        with (patch.object(event.random, "random", return_value=0),
              patch.object(event.random, "choice", return_value=event.CANDY_NAMES[0])):
            mob = NS(loot_items=[], template_vnum=444, experience_reward=90,
                     room_vnum=999, tailed_beast_key=None, shadow_clone_owner=None)
            loot = seasonal_events.mob_loot(mob, self.halloween_date)
            self.assertEqual(loot, [event.CANDY_NAMES[0]])
            boss = combat.mobs_in_room(100019)[0]
            boss_loot = seasonal_events.mob_loot(boss, self.halloween_date)
            self.assertIn(event.MASK, boss_loot)
        self.assertEqual(event.boss_loot(boss, date(2026, 11, 2)), [])

    def test_masks_are_wearable_outside_week(self):
        self.build()
        self.assertEqual(self.item_templates[event.MASK_VNUM]["stat_bonuses"]["max_health"], 175)
        event.sync(date(2026, 11, 2))
        self.player.inventory.append(event.MASK)
        before = self.player.maximum_health
        with patch.object(commands, "_fire_item_trigger"):
            commands.cmd_wear(self.session, ["pumpkin", "king", "cursed", "mask"])
        self.assertEqual(self.player.maximum_health, before + 175)

    def test_daily_treat_and_timed_respawn(self):
        self.build()
        self.player.room_vnum = 100014
        with (patch.object(event, "active", return_value=True),
              patch.object(event.random, "random", return_value=1),
              patch.object(event.random, "choice", return_value=event.CANDY_NAMES[1]),
              patch("storage.save_player")):
            event.command_trickortreat(self.session, [])
            self.assertIn(event.CANDY_NAMES[1], self.player.inventory)
            event.command_trickortreat(self.session, [])
            self.assertIn("one trick or treat", self.session.send.call_args.args[0].lower())
        boss = combat.mobs_in_room(100019)[0]
        combat.remove_mob(boss)
        event.mob_defeated(boss, now=1000)
        event._spawn_population(1000 + event.BOSS_RESPAWN_SECONDS - 1)
        self.assertEqual(len(combat.mobs_in_room(100019)), 0)
        event._spawn_population(1000 + event.BOSS_RESPAWN_SECONDS)
        self.assertEqual(len(combat.mobs_in_room(100019)), 1)

    def test_event_candy_works_after_halloween(self):
        self.build()
        event.sync(date(2026, 11, 2))
        self.player.inventory.append(event.CANDY_NAMES[0])
        self.player.health = max(0, self.player.health - 120)
        with patch("storage.save_player"):
            self.assertTrue(event.consume_candy(self.session, "candy corn"))
        self.assertNotIn(event.CANDY_NAMES[0], self.player.inventory)
        self.assertGreater(self.player.holiday_xp_boost_until, 0)


if __name__ == "__main__":
    unittest.main()
