"""Ninja Arts/Bukijutsu item, trap, and element regression checks."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import content
import data_jutsu
import leveling
import ninja_arts
import olc
import world
from models import Player


class NinjaArtsTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Arts", "Arts", primary_class="bukijutsu", level=75)
        self.player.room_vnum = 1
        self.player.chakra = 500
        self.player.stamina = 500
        self.session = NS(player=self.player, send=Mock())
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(self.player)

    def test_all_arts_unlock_and_element_gate(self):
        entries = [j for j in data_jutsu.JUTSU.values() if j["jutsu_id"].startswith("arts_")]
        self.assertEqual(len(entries), 13)
        self.assertIn("Weapon Enchantment", self.player.learned_skills)
        self.assertNotIn("Water Release: Glue Technique", self.player.learned_skills)
        self.player.chakra_nature = "wind"
        self.player.equipment["wielded"] = "A Mighty Fan"
        self.assertTrue(combat._can_use_jutsu(self.player, data_jutsu.JUTSU["fan techniques"], "fan techniques"))
        self.player.equipment.clear()
        self.assertFalse(combat._can_use_jutsu(self.player, data_jutsu.JUTSU["fan techniques"], "fan techniques"))

    def test_item_bound_enchant_and_combat(self):
        content._register_shared_items()
        self.player.inventory = ["A Basic Kunai", "A Basic Kunai"]
        ninja_arts.use_weapon_art(self.session, "weapon enchantment", ["kunai", "sharp"])
        self.assertEqual(self.player.inventory.count("A Basic Kunai"), 1)
        tagged = self.player.inventory[0]
        self.assertEqual(ninja_arts.property_of(tagged), "sharp")
        self.player.equipment["wielded"] = tagged
        self.assertEqual(ninja_arts.weapon_hit(self.player, self.player, 40), 44)
        self.player.cooldowns.clear()
        ninja_arts.use_weapon_art(self.session, "disenchantment", ["kunai"])
        self.assertEqual(self.player.inventory, ["A Basic Kunai", "A Basic Kunai"])

    def test_arts_update_a_wielded_weapon_without_an_inventory_copy(self):
        content._register_shared_items()
        self.player.equipment["wielded"] = "A Basic Kunai"
        self.player.inventory = []
        ninja_arts.use_weapon_art(self.session, "weapon enchantment", ["kunai", "sharp"])
        self.assertEqual(self.player.inventory, [])
        self.assertEqual(ninja_arts.property_of(self.player.equipment["wielded"]), "sharp")
        self.assertEqual(ninja_arts.weapon_hit(self.player, self.player, 40), 44)
        self.player.cooldowns.clear()
        ninja_arts.use_weapon_art(self.session, "disenchantment", ["kunai"])
        self.assertEqual(self.player.equipment["wielded"], "A Basic Kunai")
        self.assertEqual(self.player.inventory, [])

    def test_traps_can_be_disabled_or_detonate(self):
        mob = combat.Mob(1, 111, "Dummy", 20, 200, 200, 1, 0, 0)
        self.assertTrue(ninja_arts.attach_trap(mob, "exploding note", self.player.name))
        self.assertFalse(ninja_arts.attach_trap(mob, "exploding note", self.player.name))
        self.player.skill_proficiencies["Trap Disabling"] = 100
        ninja_arts.use_disable(self.session, mob)
        self.assertNotIn("exploding note", mob.active_status_effects)
        ninja_arts.attach_trap(mob, "poison gas bomb", self.player.name)
        with patch.object(ninja_arts.random, "randint", return_value=12):
            self.assertEqual(ninja_arts.detonate_trap(mob, "poison gas bomb"), 12)
        self.assertIn("poisoned", mob.active_status_effects)

    def test_shop_prototypes_exist(self):
        content._register_shared_items()
        for name in ("An Exploding Note", "A Smoke Bomb", "A Poison Gas Bomb", "A Wad of Exploding Clay", "A Mighty Fan", "A Pot of Glue"):
            self.assertTrue(any(proto["short_desc"] == name for proto in olc.OBJECT_TEMPLATES.values()))

    def test_fan_push_respects_open_exits_and_moves_mob(self):
        source = world.Room(1, "source", "source")
        destination = world.Room(2, "destination", "destination")
        source.exits["north"] = 2
        target = combat.Mob(4, 444, "Target", 20, 200, 200, 1, 0, 0)
        self.session.combat_target = target
        with patch.object(world.WORLD, "get", side_effect={1: source, 2: destination}.get), \
             patch.object(combat, "MOBS_BY_ROOM", {1: [target], 2: []}):
            source.exit_flags["north"] = ["door"]
            self.assertFalse(ninja_arts.fan_push(self.session, target, "north"))
            self.assertEqual(target.room_vnum, 1)
            source.exit_door_open["north"] = True
            self.assertTrue(ninja_arts.fan_push(self.session, target, "north"))
            self.assertEqual(target.room_vnum, 2)
            self.assertIsNone(self.session.combat_target)

    def test_multi_throw_consumes_three_and_drops_them(self):
        self.player.inventory = ["A Throwing Shuriken"] * 3
        target = combat.Mob(2, 222, "Target", 20, 200, 200, 1, 0, 0)
        room = NS(biome="none", ground_items=[], kekkei_no_me_caster=None)
        with patch.object(combat.world.WORLD, "get", return_value=room), \
             patch.object(combat.random, "randint", return_value=1):
            combat.use_jutsu(self.session, "multi-shuriken throw", target)
        self.assertEqual(len(self.player.inventory), 0)
        self.assertEqual(len(room.ground_items), 3)
        self.assertLess(target.health, 200)

    def test_note_is_consumed_and_detonates_on_tick(self):
        self.player.inventory = ["An Exploding Note"]
        target = combat.Mob(2, 222, "Target", 20, 200, 200, 1, 0, 0)
        room = NS(biome="none", ground_items=[], kekkei_no_me_caster=None)
        with patch.object(combat.world.WORLD, "get", return_value=room), \
             patch.object(combat.random, "randint", return_value=1):
            combat.use_jutsu(self.session, "exploding note", target)
        self.assertFalse(self.player.inventory)
        self.assertFalse(room.ground_items)
        self.assertEqual(target.active_status_effects["exploding note"]["duration"], 2)
        with patch.object(combat, "MOBS_BY_ROOM", {1: [target]}), \
             patch.object(ninja_arts.random, "randint", return_value=28):
            combat.tick_all_mob_effects([self.session])
            self.assertEqual(target.health, 200)
            combat.tick_all_mob_effects([self.session])
        self.assertEqual(target.health, 172)
        self.assertNotIn("exploding note", target.active_status_effects)


if __name__ == "__main__":
    unittest.main()
