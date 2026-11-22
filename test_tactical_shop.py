"""Mob 785 tactical stock, real antidote cure and persistent room tags."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import consumables
import content
import data_shops
import leveling
import olc
import room_trap_tags
import shop_flags
import skill_training
import storage
import tactical_shop
import world
from models import Player


class TacticalShopTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.objects = {}
        self.mobs = {785: combat.default_template(785, "a tactical supply merchant")}
        self.game_world = world.World()
        self.room = world.Room(886661, "Training road", "An open training road.", safe=False)
        self.game_world.add_room(self.room)
        for obj, key, value in (
            (storage, "DATA_DIR", self.temporary.name),
            (olc, "OBJECT_TEMPLATES", self.objects),
            (combat, "MOB_TEMPLATES", self.mobs),
            (world, "WORLD", self.game_world),
        ):
            ctx = patch.object(obj, key, value)
            ctx.start()
            self.addCleanup(ctx.stop)
        self.addCleanup(setattr, room_trap_tags, "_loaded_path", None)
        self.addCleanup(setattr, room_trap_tags, "_records", {})
        self.saver = patch.object(storage, "save_player")
        self.saver.start()
        self.addCleanup(self.saver.stop)
        self.growth = patch.object(combat, "grow_skill_from_usage")
        self.growth.start()
        self.addCleanup(self.growth.stop)
        self.immortal = patch.object(combat, "is_immortal_immune_to_defeat",
                                     return_value=False)
        self.immortal.start()
        self.addCleanup(self.immortal.stop)
        room_trap_tags._loaded_path = None
        room_trap_tags._records = {}
        # Real existing name/VNUM definitions from content's fixed catalog.
        for vnum, name in tactical_shop.EXPLOSIVES:
            obj = olc.default_object(vnum, name)
            obj.update(item_type="misc", level=0, cost={
                9803: 60, 9804: 70, 9805: 100, 9806: 150}[vnum])
            self.objects[vnum] = obj

    def make_player(self, name, org="anbu", level=250):
        player = Player(name, name, level=level, primary_class="bukijutsu",
                        room_vnum=self.room.vnum)
        player.pvp_organization = org
        player.health = player.maximum_health = 6000
        player.chakra = player.maximum_chakra = 50000
        player.stamina = player.maximum_stamina = 50000
        player.ryo = 900000
        player.learned_skills = []
        player.practice_gate_enabled = True
        leveling.sync_universal_skills(player)
        skill_training.mark_practiced(player, room_trap_tags.SKILL_NAME)
        output = []
        return player, NS(player=player, send=output.append), output

    def test_shop_785_stocks_only_working_supplies_and_antidote(self):
        # Previously stocked glue, healing supplies, and unrelated builder
        # goods are handled without rewriting player /data.
        unwanted = [(99001, "A Pot of Glue", "misc"),
                    (99002, "A Healing Salve", "medical"),
                    (99003, "A Soldier Pill", "medical"),
                    (99004, "Medicinal Herbs", "misc")]
        for vnum, name, kind in unwanted:
            self.objects[vnum] = olc.default_object(vnum, name)
            self.objects[vnum]["item_type"] = kind
        custom = olc.default_object(99005, "A Builder Custom Item")
        custom["item_type"] = "misc"
        self.objects[99005] = custom
        self.mobs[785]["shop_items"] = [*range(99001, 99006)]
        original = list(self.mobs[785]["shop_items"])
        result = tactical_shop.install()
        self.assertTrue(result["mob_exists"])
        self.assertEqual(result["excluded"], tuple(original[:4]))
        self.assertEqual(result["conflicts"], ())
        expected = [v for v, _ in tactical_shop.catalog()]
        self.assertEqual(len(expected), 14)
        self.assertEqual(set(expected),
                         set(range(80, 89)) | set(range(9803, 9807)) | {89})
        self.assertEqual(self.mobs[785]["shop_items"], [99005] + expected)
        self.assertEqual(shop_flags.specialty_from_flags(self.mobs[785]), "tactical")
        self.assertTrue(data_shops.can_sell_here("tactical", "misc"))
        self.assertTrue(data_shops.can_sell_here("tactical", "medical"))
        self.assertFalse(data_shops.can_sell_here("tactical", "armor"))
        antidote = self.objects[89]
        self.assertEqual(antidote["short_desc"], "Antidote Pill")
        self.assertEqual(antidote["item_type"], "medical")
        self.assertFalse(antidote["extra_flags"])
        self.assertEqual(antidote["heal_amount"], 0)
        self.assertEqual((antidote["level"], antidote["cost"]), (25, 750))
        self.assertFalse(tactical_shop.install()["added"])
        self.assertEqual(self.mobs[785]["shop_items"], [99005] + expected)

    def test_occupied_antidote_vnum_is_protected_and_not_stocked(self):
        original = olc.default_object(89, "An Old Builder Relic")
        self.objects[89] = original
        info = tactical_shop.install()
        self.assertIn(89, info["conflicts"])
        self.assertNotIn(89, self.mobs[785]["shop_items"])
        self.assertIs(self.objects[89], original)

    def test_missing_builder_shop_is_not_fabricated(self):
        self.mobs.clear()
        output = tactical_shop.install()
        self.assertFalse(output["mob_exists"])
        self.assertEqual(self.mobs, {})

    def test_real_shop_list_buy_and_antidote_only_cures_poison(self):
        tactical_shop.install()
        player, _session, logs = self.make_player("Buyer")
        session = NS(player=player, send=logs.append)
        merchant = NS(name="a tactical supply merchant", template_vnum=785,
                      room_vnum=self.room.vnum, player_shop_owner=None)
        with patch.object(commands, "_own_kage_chamber", return_value=False), \
             patch.object(commands, "_find_shopkeeper", return_value=merchant), \
             patch.object(commands.npc_schedules, "shop_is_open", return_value=True), \
             patch.object(commands, "_fire_item_trigger"):
            commands.cmd_list(session, [])
            listing = logs[-1]
            for vnum, name in tactical_shop.catalog():
                self.assertIn(name, listing)
            self.assertIn("[Lvl 100]", listing)
            commands.cmd_buy(session, ["antidote"])
        self.assertIn("Antidote Pill", player.inventory)
        self.assertEqual(player.ryo, 899250)
        player.active_status_effects["poisoned"] = {"duration": 3}
        before = (player.health, player.chakra, player.stamina)
        consumables.consume(session, "use", "antidote")
        self.assertNotIn("poisoned", player.active_status_effects)
        self.assertNotIn("Antidote Pill", player.inventory)
        self.assertEqual(before, (player.health, player.chakra, player.stamina))
        player.inventory.append("Antidote Pill")
        consumables.consume(session, "eat", "antidote")
        self.assertIn("Antidote Pill", player.inventory)
        self.assertIn("not poisoned", logs[-1])

    def test_all_thirteen_supplies_are_placeable_persistent_and_trigger(self):
        tactical_shop.install()
        owner, owner_session, _ = self.make_player("TagSetter")
        victim, victim_session, output = self.make_player("Enemy", "root")
        for key in (*room_trap_tags.TAGS, *room_trap_tags.EXISTING):
            with self.subTest(tag=key):
                tag_name = room_trap_tags._physical_item(key)[0]
                owner.cooldowns.clear()
                owner.inventory.append(tag_name)
                output.clear()
                commands.cmd_trap(owner_session, ["place", key])
                self.assertNotIn(tag_name, owner.inventory)
                self.assertTrue(os.path.isfile(room_trap_tags._path()))
                # Simulate a process restart without touching /data.
                room_trap_tags._records = {}
                room_trap_tags._loaded_path = None
                room_trap_tags.load()
                pending = room_trap_tags._records[str(self.room.vnum)]
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["type"], key)
                victim.active_status_effects.clear()
                room_trap_tags.on_enter(victim_session)
                self.assertIn("trigger", " ".join(output))
                self.assertNotIn(str(self.room.vnum), room_trap_tags._records)
                # The consumed trap is removed from the persisted ledger.
                room_trap_tags._loaded_path = None
                room_trap_tags.load()
                self.assertNotIn(str(self.room.vnum), room_trap_tags._records)
        self.assertEqual(len(owner.inventory), 0)


if __name__ == "__main__":
    unittest.main()
