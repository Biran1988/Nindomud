"""Selected Ninjutsu expansion: unlocks, elements, clones, and buffs."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import derived_stats
import leveling
import status_effects
from models import Player


class NinjutsuExpansionTests(unittest.TestCase):
    def player(self, level=75, nature="lightning"):
        p = Player(name="Nin", account_name="Nin", primary_class="ninjutsu", level=level)
        p.chakra_nature = nature
        p.chakra = 500
        p.room_vnum = 1
        return p

    def test_unlocks_and_element_assignments(self):
        p = self.player(75)
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(p)
            other = Player(name="Other", account_name="Other", primary_class="taijutsu", level=75)
            leveling.sync_universal_skills(other)
        self.assertIn("Chakra Ball", p.learned_skills)
        self.assertIn("Maximum Chidori", p.learned_skills)
        self.assertIn("Barrier", p.learned_skills)
        self.assertNotIn("Juuha Shou", other.learned_skills)
        self.assertIn("Barrier", other.learned_skills)
        for nature in ("fire", "water", "wind", "earth", "lightning"):
            self.assertEqual(data_jutsu.JUTSU[f"{nature} rasengan"]["element"], nature)
        self.assertEqual(data_jutsu.match_prefix(["doton", "rasengan", "enemy"]), ("earth rasengan", 2))
        for key in ("chidori", "dual chidori", "full body chidori", "maximum chidori", "raikiri"):
            self.assertEqual(data_jutsu.JUTSU[key]["element"], "lightning")
        self.assertEqual(data_jutsu.JUTSU["juuha shou"]["element"], "wind")
        self.assertEqual(commands.CHAKRA_NATURE_MIN_LEVEL, 25)

    def test_chakra_paper_reveals_at_25(self):
        p = self.player(24, "water")
        p.inventory = ["A Sheet of Chakra Paper"]
        s = NS(player=p, send=Mock())
        with patch.object(commands, "_find_object_prototype_by_name", return_value={"item_type": "misc"}):
            commands.cmd_channel(s, ["chakra", "paper"])
            self.assertFalse(p.chakra_nature_revealed)
            self.assertEqual(len(p.inventory), 1)
            p.level = 25
            commands.cmd_channel(s, ["chakra", "paper"])
        self.assertTrue(p.chakra_nature_revealed)
        self.assertEqual(p.inventory, [])

    def test_element_gate_and_water_room(self):
        p = self.player(50, "wind")
        p.learned_skills = ["Juuha Shou", "Suigadan", "Rasengan"]
        self.assertTrue(combat._can_use_jutsu(p, data_jutsu.JUTSU["juuha shou"], "juuha shou"))
        self.assertFalse(combat._can_use_jutsu(p, data_jutsu.JUTSU["suigadan"], "suigadan"))
        self.assertTrue(combat._can_use_jutsu(p, data_jutsu.JUTSU["rasengan"], "rasengan"))
        p.chakra_nature = "water"
        with patch.object(combat.world.WORLD, "get", return_value=NS(biome="forest")):
            self.assertFalse(combat._can_use_jutsu(p, data_jutsu.JUTSU["suigadan"], "suigadan"))
        with patch.object(combat.world.WORLD, "get", return_value=NS(biome="river")):
            self.assertTrue(combat._can_use_jutsu(p, data_jutsu.JUTSU["suigadan"], "suigadan"))

    def test_clone_mastery_gate_and_distinct_live_clone(self):
        p = self.player(50, "water")
        p.learned_skills = ["Mizu Bunshin", "Shadow Clone Jutsu"]
        s = NS(player=p, pending_cast=None, send=Mock())
        with patch.object(combat, "MOBS_BY_ROOM", {}), patch.object(combat, "MOB_TEMPLATES", {}):
            p.skill_proficiencies["Shadow Clone Jutsu"] = 99
            combat.use_elemental_clone_jutsu(s, "mizu bunshin")
            self.assertFalse(combat.active_shadow_clones(p))
            p.skill_proficiencies["Shadow Clone Jutsu"] = 100
            combat.use_elemental_clone_jutsu(s, "mizu bunshin")
            clones = combat.active_shadow_clones(p)
            self.assertEqual(len(clones), 1)
            self.assertEqual(clones[0].clone_element, "water")
            self.assertIn("water clone", clones[0].name)
            self.assertEqual(clones[0].max_health, p.maximum_health // 4)

    def test_barrier_and_room_earthquake(self):
        p = self.player(50, "earth")
        p.learned_skills = ["Barrier", "Chishin"]
        s = NS(player=p, pending_cast=None, send=Mock())
        base_ac = derived_stats.armor_class(p)
        commands.cmd_use_jutsu(s, "barrier", [])
        self.assertEqual(derived_stats.armor_class(p), base_ac)
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects, 100), 90)
        for _ in range(5):
            status_effects.tick_effects(p.active_status_effects)
        self.assertEqual(derived_stats.armor_class(p), base_ac)
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects, 100), 100)
        a = combat.Mob(1, 100, "one", 50, 1000, 1000, 1, 0, 0)
        b = combat.Mob(2, 101, "two", 50, 1000, 1000, 1, 0, 0)
        with patch.object(combat, "mobs_in_room", return_value=[a, b]), \
             patch.object(combat.random, "randint", return_value=1), \
             patch.object(combat, "roll_jutsu_damage", return_value=(50, False)), \
             patch.object(combat, "_jutsu_damage_bonus", return_value=0):
            combat.use_jutsu(s, "chishin", a)
        self.assertLess(a.health, 1000)
        self.assertEqual(a.health, b.health)

    def test_elemental_clone_assists_in_pvp(self):
        attacker = self.player(50, "lightning")
        defender = Player(name="Defender", account_name="Defender", primary_class="taijutsu", level=50)
        defender.room_vnum = attacker.room_vnum
        attacker_session = NS(player=attacker, send=Mock())
        defender_session = NS(player=defender, send=Mock())
        clone = NS(clone_element="lightning")
        before = defender.health
        with patch.object(combat.random, "randint", side_effect=[1, 100, 1]), \
             patch.object(combat, "_player_attack_damage", return_value=40):
            combat._clone_attack_target_once(attacker_session, attacker, defender_session, defender, clone)
        self.assertLess(defender.health, before)
        self.assertIn("paralyzed", defender.active_status_effects)


if __name__ == "__main__":
    unittest.main()
