"""KKGK practises, indestructible VNUM 6, and admin job level rewards."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import jobs
import olc
from models import Player


class BloodlinePracticeCategoryTests(unittest.TestCase):
    def test_eye_techniques_have_exclusive_category(self):
        categories = commands.PRAC_CATEGORY_ORDER
        self.assertIn("KKGK", categories)
        kkgk = {name for name, _ in commands._skill_catalog_for_category("KKGK")}
        for name in ("Tsukuyomi", "Amaterasu", "Kamui: Pocket Dimension",
                     "Byakugan", "Gentle Fist: Chakra Point Strike", "Tenseigan Chakra Mode"):
            self.assertIn(name, kkgk)
            self.assertEqual(commands._category_for_skill(name), "KKGK")
            for class_category in ("Ninjutsu", "Taijutsu", "Genjutsu", "Bukijutsu", "General Skills"):
                self.assertNotIn(name, {value for value, _ in commands._skill_catalog_for_category(class_category)})
        for jutsu in data_jutsu.JUTSU.values():
            if jutsu.get("kkg_gate"):
                self.assertEqual(commands._category_for_skill(jutsu["display_name"]), "KKGK")

    def test_bloodline_uses_original_teacher_and_original_cast_class(self):
        self.assertEqual(commands._categorize_underlying_class("Tsukuyomi"), "Genjutsu")
        self.assertEqual(commands._categorize_underlying_class("Byakugan"), "General Skills")
        self.assertEqual(data_jutsu.JUTSU["tsukuyomi"]["class_requirement"], "genjutsu")
        self.assertEqual(data_jutsu.JUTSU["byakugan"]["class_requirement"], "general")

    def test_prac_display_is_in_kkgk_section_once(self):
        player = Player("Eye", "Eye")
        player.learned_skills.extend(["Tsukuyomi", "Byakugan"])
        session = NS(player=player, send=Mock())
        commands.cmd_prac(session, [])
        text = session.send.call_args.args[0]
        self.assertIn("[ KKGK ]", text)
        self.assertEqual(text.count("Tsukuyomi"), 1)
        self.assertEqual(text.count("Byakugan"), 1)


class ImmortalTrainingDummyTests(unittest.TestCase):
    def setUp(self):
        template = combat.default_template(6, "an ancient shinobi practice dummy")
        template.update({"level": 240, "enabled": False, "hit_dice": "1d1+1",
                         "damage_dice": "3d999+100", "auto_balance": True,
                         "experience_reward": 9999, "ryo_reward": 99999,
                         "act_flags": ["Npc", "Wander", "Immortal"], "teacher": "ninjutsu",
                         "shopkeeper": True, "gambler": True})
        self.repo = patch.object(combat, "MOB_TEMPLATES", {6: template})
        self.rooms = patch.object(combat, "MOBS_BY_ROOM", {})
        self.repo.start(); self.rooms.start()
        self.addCleanup(self.repo.stop); self.addCleanup(self.rooms.stop)

    def test_legacy_immortal_mob_is_targetable_and_outside_global_scaling(self):
        mob = combat.spawn_mob(6, 67890)
        self.assertIsNotNone(mob)
        self.assertEqual(mob.level, 240)
        self.assertEqual(mob.max_health, combat.TRAINING_DUMMY_HEALTH)
        self.assertEqual(mob.health, combat.TRAINING_DUMMY_HEALTH)
        self.assertEqual((mob.experience_reward, mob.ryo_reward), (0, 0))
        self.assertEqual(combat._mob_attack_damage(mob), 0)
        self.assertFalse(combat.is_immortal_mob(mob))
        self.assertFalse(combat.is_teacher(mob))
        self.assertFalse(combat.is_shopkeeper(mob))
        self.assertFalse(combat.is_gambler(mob))
        self.assertFalse(combat.is_wandering(mob))
        mob.health -= 10**10
        self.assertEqual(mob.health, mob.max_health)
        mob.health = 0
        self.assertEqual(mob.health, mob.max_health)

    def test_dummy_cannot_be_defeated_and_cannot_reward_players(self):
        mob = combat.spawn_mob(6, 67890)
        player = Player("Trainee", "Trainee", room_vnum=67890)
        session = NS(player=player, send=Mock())
        before = (player.npc_kills, player.experience, player.ryo)
        combat.handle_mob_defeat(session, mob)
        self.assertEqual((player.npc_kills, player.experience, player.ryo), before)
        self.assertIn(mob, combat.mobs_in_room(67890))

    def test_dummy_does_not_retalitate_but_player_melee_is_resolved(self):
        mob = combat.spawn_mob(6, 67890)
        player = Player("Trainee", "Trainee", room_vnum=67890)
        player.health = 140
        session = NS(player=player, combat_target=mob, pvp_target=None, send=Mock(),
                     pending_cast=None, controlled_clone=None)
        with patch.object(combat, "_player_attack_mob_once") as attack, \
             patch.object(combat, "_roll_extra_attacks", return_value=0), \
             patch.object(combat, "_offhand_attack"), \
             patch.object(combat, "_resolve_summon_round"), \
             patch("ninja_arts.tick_samurai_sabre"), \
             patch("sage_mode.combat_pulse"), \
             patch("sage_mode.extra_attacks", return_value=0):
            combat.resolve_pulse(session)
            attack.assert_called_once()
        self.assertEqual(player.health, 140)
        self.assertIs(session.combat_target, mob)


class StaffJobLevelTests(unittest.TestCase):
    def setUp(self):
        self.target = Player("Learner", "Learner", level=60)
        self.staff = NS(account=NS(staff_level="administrator"),
                        player=NS(name="Admin"), send=Mock())
        self.guard = patch.object(olc, "_require_admin", return_value=True)
        self.lookup = patch.object(olc, "_find_target_player", return_value=(self.target, None))
        self.save = patch.object(olc.storage, "save_player")
        self.log = patch.object(olc, "_log")
        self.notice = patch("shinobi_notices.announce_level")
        for p in (self.guard, self.lookup, self.save, self.log, self.notice):
            p.start();self.addCleanup(p.stop)

    def test_farming_job_level_reward_applies_real_stat_bonus_and_saves(self):
        old_stamina = self.target.maximum_stamina
        olc.cmd_levelup(self.staff, ["Learner", "job", "farming"])
        self.assertEqual(self.target.job_levels["farming"], 2)
        self.assertEqual(self.target.job_xp["farming"], jobs.job_xp_for_level(2))
        self.assertEqual(self.target.maximum_stamina, old_stamina + 3)
        self.assertEqual(self.target.level, 60)
        self.staff.send.assert_called()

    def test_short_alias_and_job_cap(self):
        olc.cmd_levelup(self.staff, ["Learner", "cooking"])
        self.assertEqual(jobs.get_job_level(self.target, "cooking"), 2)
        self.target.job_levels["cooking"] = jobs.MAX_JOB_LEVEL
        self.staff.send.reset_mock()
        olc.cmd_levelup(self.staff, ["Learner", "job", "cooking"])
        self.assertIn("cap", self.staff.send.call_args.args[0])
        self.assertEqual(jobs.get_job_level(self.target, "cooking"), jobs.MAX_JOB_LEVEL)

    def test_invalid_job_is_refused(self):
        olc.cmd_levelup(self.staff, ["Learner", "job", "badjob"])
        self.assertIn("Unknown job", self.staff.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
