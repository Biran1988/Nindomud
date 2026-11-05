"""Regression coverage for immortal NPC protection and attack/style progression."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import sword_styles
from models import Player


class ImmortalMobProtectionTests(unittest.TestCase):
    def setUp(self):
        self.vnum = 987912
        self.flags = ["Npc", "Immortal"]
        template = {"act_flags": self.flags}
        self.template_patch = patch.dict(combat.MOB_TEMPLATES, {self.vnum: template})
        self.template_patch.start()
        self.addCleanup(self.template_patch.stop)
        self.mob = combat.Mob(1, self.vnum, "the eternal keeper", 10,
                              120, 120, 100, 500, 250)
        self.world_patch = patch.dict(combat.MOBS_BY_ROOM, {100: [self.mob]})
        self.world_patch.start()
        self.addCleanup(self.world_patch.stop)
        self.player = Player("Attacker", "Attacker", room_vnum=100)
        self.session = NS(player=self.player, combat_target=None, send=Mock())
        self.assertTrue(combat.is_immortal_mob(self.mob))

    def test_direct_hit_and_lethal_damage_are_ignored(self):
        for damage in (25, 999999):
            self.mob.health -= damage
            self.assertEqual(self.mob.health, self.mob.max_health)
        self.mob.health = 0
        self.assertEqual(self.mob.health, 120)

    def test_start_attack_and_command_reject_immortal(self):
        combat.start_attack(self.session, self.mob)
        self.assertIsNone(self.session.combat_target)
        self.assertIn("cannot be attacked", str(self.session.send.call_args))
        self.session.send.reset_mock()
        commands.cmd_attack(self.session, ["eternal", "keeper"])
        self.assertIsNone(self.session.combat_target)
        self.assertIn("cannot be attacked", str(self.session.send.call_args))

    def test_direct_jutsu_rejected_before_cost_or_combat(self):
        combat.use_jutsu(self.session, "dynamic entry", self.mob)
        self.assertEqual(self.mob.health, 120)
        self.assertIn("cannot be attacked", str(self.session.send.call_args))

    def test_defeat_guard_prevents_rewards_and_despawn(self):
        self.mob.health = -5000
        before = (self.player.experience, self.player.ryo, self.player.npc_kills)
        combat.handle_mob_defeat(self.session, self.mob)
        self.assertEqual((self.player.experience, self.player.ryo, self.player.npc_kills), before)
        self.assertIn(self.mob, combat.mobs_in_room(100))
        self.assertEqual(self.mob.health, 120)

    def test_existing_burns_poison_and_traps_are_cleared(self):
        self.mob.active_status_effects.update({
            "burning": {"duration": 3},
            "poisoned": {"duration": 4},
            "bleeding": {"duration": 1},
            "explosive_trap": {"duration": 1, "source": "Tester"},
        })
        self.mob.mangekyo_amaterasu_caster = "Tester"
        combat.tick_all_mob_effects()
        self.assertEqual(self.mob.health, 120)
        self.assertIsNone(self.mob.mangekyo_amaterasu_caster)
        self.assertFalse(any(x in self.mob.active_status_effects for x in
                             ("burning", "poisoned", "bleeding")))

    def test_flag_changes_work_on_existing_mob(self):
        self.flags.remove("Immortal")
        self.assertFalse(combat.is_immortal_mob(self.mob))
        self.mob.health -= 10
        self.assertEqual(self.mob.health, 110)
        self.flags.append("Immortal")
        self.mob.health -= 10
        self.assertEqual(self.mob.health, 120)


class NumberedAttackRulesTests(unittest.TestCase):
    def test_non_bukijutsu_unlock_is_level_100(self):
        for cls in ("ninjutsu", "taijutsu", "genjutsu"):
            player = Player("Tester", "Tester", primary_class=cls)
            self.assertEqual(data_jutsu.multi_attack_required_level(
                player, "Second Attack", 25), 100)
        buki = Player("Smith", "Smith", primary_class="bukijutsu")
        self.assertEqual(data_jutsu.multi_attack_required_level(buki, "Second Attack", 25), 25)

    def test_maximum_mastery_reliably_produces_numbered_attacks(self):
        player = Player("Blade", "Blade", primary_class="bukijutsu", level=100)
        player.learned_skills = ["Second Attack", "Third Attack", "Fourth Attack"]
        player.skill_proficiencies = {name: 100 for name in player.learned_skills}
        with patch.object(combat.random, "randint", return_value=100):
            self.assertEqual(combat._roll_extra_attacks(player), 3)  # four total
        player.learned_skills.append("Fifth Attack")
        player.skill_proficiencies["Fifth Attack"] = 100
        with patch.object(combat.random, "randint", return_value=100):
            self.assertEqual(combat._roll_extra_attacks(player), 4)  # five total

    def test_legacy_early_unlock_cannot_bypass_level_requirement(self):
        player = Player("OldPlayer", "OldPlayer", primary_class="genjutsu", level=99)
        player.learned_skills = ["Second Attack", "Third Attack"]
        player.skill_proficiencies = {"Second Attack": 100, "Third Attack": 100}
        self.assertEqual(combat._roll_extra_attacks(player), 0)
        player.level = 100
        self.assertEqual(combat._roll_extra_attacks(player), 1)  # Third belongs to Bukijutsu only

    def test_third_fourth_fifth_attacks_are_bukijutsu_only(self):
        for name, level, requirement in data_jutsu.MULTI_ATTACK_SKILLS[1:]:
            self.assertEqual(requirement, "bukijutsu", name)
            self.assertIn((name, level), commands._skill_catalog_for_category("Bukijutsu"))
            self.assertNotIn(name, dict(commands._skill_catalog_for_category("General Skills")))
            self.assertEqual(commands._category_for_skill(name), "Bukijutsu")
            self.assertEqual(commands._categorize_underlying_class(name), "Bukijutsu")
        for cls in ("ninjutsu", "taijutsu", "genjutsu"):
            player = Player("Tester", "Tester", level=250, primary_class=cls)
            player.learned_skills = [name for name, _, _ in data_jutsu.MULTI_ATTACK_SKILLS]
            player.skill_proficiencies = {name: 100 for name in player.learned_skills}
            self.assertEqual(combat._roll_extra_attacks(player), 1)
            import leveling
            leveling.sync_universal_skills(player)
            self.assertEqual(player.learned_skills.count("Second Attack"), 1)
            self.assertFalse(set(player.learned_skills) & {"Third Attack", "Fourth Attack", "Fifth Attack"})
            self.assertEqual(player.skill_proficiencies["Third Attack"], 100)

    def test_bukijutsu_attack_requires_bukijutsu_teacher(self):
        self.assertEqual(commands._categorize_underlying_class("Third Attack"), "Bukijutsu")


class SwordSchoolTests(unittest.TestCase):
    def test_progression_starts_85_ends_with_aggressive_250(self):
        self.assertEqual(list(sword_styles.STYLES.values())[0]["level"], 85)
        self.assertEqual(sword_styles.STYLES["Jigen Ryu"]["level"], 250)
        self.assertEqual(sword_styles.STYLES["Jigen Ryu"]["damage"],
                         max(s["damage"] for s in sword_styles.STYLES.values()))

    def test_school_requires_class_sword_and_stamina(self):
        player = Player("SwordUser", "SwordUser", level=250, primary_class="bukijutsu")
        player.learned_skills = ["Jigen Ryu"]
        player.skill_proficiencies = {"Jigen Ryu": 100}
        player.sword_style = "Jigen Ryu"
        player.stamina = 100
        player.equipment["wielded"] = "A Basic Ninja Sword"
        self.assertIsNotNone(sword_styles.selected(player))
        self.assertEqual(sword_styles.damage_bonus(player, 100), 145)
        player.stamina = 0
        self.assertIsNone(sword_styles.selected(player))
        player.stamina = 100
        player.primary_class = "ninjutsu"
        self.assertIsNone(sword_styles.selected(player))

    def test_landed_sword_strike_spends_stamina_and_trains(self):
        player = Player("SwordUser", "SwordUser", level=250, primary_class="bukijutsu")
        player.learned_skills = ["Jigen Ryu"]
        player.skill_proficiencies = {"Jigen Ryu": 50}
        player.sword_style = "Jigen Ryu"
        player.stamina = 100
        player.equipment["wielded"] = "A Basic Ninja Sword"
        session = NS(player=player, send=Mock())
        with patch.object(combat, "grow_skill_from_usage") as grow:
            sword_styles.successful_strike(player, session)
        self.assertEqual(player.stamina, 90)
        grow.assert_called_once_with(player, "Jigen Ryu", session=session)


if __name__ == "__main__":
    unittest.main()
