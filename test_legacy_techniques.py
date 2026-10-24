"""Selected old-MUD skills and the scroll-only instant-kill gate."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import combat
import commands
import content
import data_jutsu
import legacy_techniques
import leveling
import olc
from models import Player
from session import Session, State


class LegacyTechniquesTests(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.session = Session(self.output.append, lambda: None)
        self.session.state = State.PLAYING
        self.player = Player("Caster", "Caster", primary_class="bukijutsu", level=80)
        self.player.room_vnum = 1
        self.player.chakra = 500
        self.player.stamina = 100
        self.session.player = self.player
        self.session.active_sessions = lambda: [self.session]
        content._register_shared_items()

    def test_class_grants_and_scroll_requires_read(self):
        self.assertIn("dual wield", data_jutsu.all_unlocked_for_class("bukijutsu", 80))
        self.assertIn("weapon expert", data_jutsu.all_unlocked_for_class("bukijutsu", 80))
        self.assertIn("chokkan", data_jutsu.all_unlocked_for_class("genjutsu", 80))
        self.assertIn("soto uke", data_jutsu.all_unlocked_for_class("taijutsu", 20))
        for category in ("bukijutsu", "genjutsu", "taijutsu", "ninjutsu"):
            self.assertNotIn("1000 years of death", data_jutsu.all_unlocked_for_class(category, 100))
        self.assertNotIn("1000 years of death", data_jutsu.all_jutsu_keys())
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(self.player)
        self.assertNotIn("1000 Years of Death", self.player.learned_skills)
        scroll = olc.OBJECT_TEMPLATES[9810]["short_desc"]
        self.player.inventory.append(scroll)
        commands.cmd_read(self.session, ["scroll", "of", "100", "years", "of", "death"])
        self.assertIn("1000 Years of Death", self.player.learned_skills)
        self.assertNotIn(scroll, self.player.inventory)

    def test_dual_wield_uses_offhand_weapon_and_can_stow_it(self):
        self.player.learned_skills = ["Dual Wield", "Weapon Expert"]
        self.player.skill_proficiencies.update({"Dual Wield": 100, "Weapon Expert": 100})
        self.player.equipment["wielded"] = "A Basic Ninja Sword"
        self.player.inventory.append("A Basic Kunai")
        commands.cmd_use_jutsu(self.session, "dual wield", ["kunai"])
        self.assertEqual(self.player.equipment["offhand"], "A Basic Kunai")
        with patch.object(combat, "_player_attack_mob_once") as attack:
            combat._offhand_attack(self.session, NS(health=100))
            self.assertEqual(attack.call_count, 1)
            self.assertEqual(self.player.equipment["wielded"], "A Basic Ninja Sword")
            self.assertEqual(self.player.stamina, 95)
        commands.cmd_remove(self.session, ["offhand"])
        self.assertNotIn("offhand", self.player.equipment)
        self.assertIn("A Basic Kunai", self.player.inventory)

    def test_chokkan_halves_a_real_pending_cast(self):
        self.player.primary_class = "genjutsu"
        self.player.learned_skills = ["Chokkan"]
        self.player.skill_proficiencies["Chokkan"] = 100
        commands.cmd_use_jutsu(self.session, "chokkan", [])
        self.assertTrue(self.player.chokkan_active)
        self.assertEqual(self.player.chakra, 475)
        with patch("data_handsigns.casting_delay_seconds", return_value=4):
            combat.begin_pending_cast(self.session, "narakumi", self.session, is_pvp=False)
        self.assertEqual(self.session.pending_cast.remaining_seconds, 2)
        self.session.pending_cast = None
        commands.cmd_use_jutsu(self.session, "chokkan", [])
        self.assertFalse(self.player.chokkan_active)

    def test_soto_uke_blocks_at_mastery_and_spends_stamina(self):
        self.player.primary_class = "taijutsu"
        self.player.learned_skills = ["Soto Uke"]
        self.player.skill_proficiencies["Soto Uke"] = 100
        with patch("combat.random.randint", side_effect=[1, 1]):
            self.assertTrue(combat._soto_uke_blocks(self.player, 80))
        self.assertEqual(self.player.stamina, 90)

    def test_death_scroll_kills_mob_through_defeat_and_respects_protection(self):
        mob = NS(name="Bandit", health=150, room_vnum=1)
        self.player.learned_skills = ["1000 Years of Death"]
        with patch.object(combat, "find_mob", return_value=mob), \
             patch.object(combat, "is_shopkeeper", return_value=False), \
             patch.object(combat, "is_gambler", return_value=False), \
             patch.object(combat, "is_teacher", return_value=False), \
             patch.object(combat, "is_immortal_mob", return_value=False), \
             patch.object(combat, "handle_mob_defeat") as defeated:
            legacy_techniques.instant_kill(self.session, ["Bandit"])
            self.assertEqual(mob.health, 0)
            defeated.assert_called_once_with(self.session, mob)
        self.assertEqual(self.player.chakra, 400)

    def test_instant_kill_obeys_pvp_safe_room_and_uses_normal_defeat(self):
        other = Session(lambda message: None, lambda: None)
        other.state = State.PLAYING
        other.player = Player("Rival", "Rival", room_vnum=1, health=200, maximum_health=200)
        self.session.active_sessions = lambda: [self.session, other]
        self.player.learned_skills = ["1000 Years of Death"]
        with patch.object(combat, "find_mob", return_value=None), \
             patch.object(legacy_techniques.world.WORLD, "get", return_value=NS(safe=True)), \
             patch.object(combat, "handle_pvp_defeat") as defeated:
            legacy_techniques.instant_kill(self.session, ["Rival"])
            self.assertEqual(other.player.health, 200)
            self.assertEqual(self.player.chakra, 500)
            defeated.assert_not_called()
        with patch.object(combat, "find_mob", return_value=None), \
             patch.object(legacy_techniques.world.WORLD, "get", return_value=NS(safe=False)), \
             patch.object(combat, "try_trigger_izanagi", return_value=False), \
             patch.object(combat, "handle_pvp_defeat") as defeated:
            legacy_techniques.instant_kill(self.session, ["Rival"])
            self.assertEqual(other.player.health, 0)
            defeated.assert_called_once_with(self.session, other, skip_mangekyo_check=True)

    def test_weapon_expert_requires_armed_bukijutsu(self):
        self.player.learned_skills = ["Weapon Expert"]
        self.player.skill_proficiencies["Weapon Expert"] = 100
        self.assertEqual(combat._weapon_expert_damage(self.player, 20), 20)
        self.player.equipment["wielded"] = "A Basic Ninja Sword"
        self.assertEqual(combat._weapon_expert_damage(self.player, 20), 30)


if __name__ == "__main__":
    unittest.main()
