"""Job XP gain messages, authentic Chakra Steel crafting, and changes log."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import changelog
import commands
import content
import jobs
import village_perks
import ninja_arts
import olc
from models import Player


class JobXpGainTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Farmer", "Farmer")
        self.player.village = "leaf"
        self.session = NS(player=self.player, send=Mock())
        # Keep base XP tests isolated from any persisted global perks.
        self.perks = patch.object(village_perks, "xp_multiplier", return_value=1.0)
        self.perks.start()
        self.addCleanup(self.perks.stop)

    def test_each_job_displays_earned_xp(self):
        for job in ("fishing", "mining", "lumberjack", "farming", "cooking", "gemcutter"):
            with self.subTest(job=job):
                self.session.send.reset_mock()
                commands._award_job_action_xp(self.session, job, 35)
                self.assertEqual(jobs.get_job_xp(self.player, job), 35)
                messages = [call.args[0] for call in self.session.send.call_args_list]
                self.assertTrue(any(f"+35 {job.capitalize()} XP" in m for m in messages))

    def test_active_triple_exp_grants_three_times_job_xp(self):
        with patch.object(village_perks, "xp_multiplier", return_value=3.0) as perk:
            for job in ("fishing", "mining", "lumberjack", "farming", "cooking", "gemcutter"):
                with self.subTest(job=job):
                    self.session.send.reset_mock()
                    commands._award_job_action_xp(self.session, job, 35)
                    perk.assert_called_with("leaf")
                    self.assertEqual(jobs.get_job_xp(self.player, job), 105)
                    messages = [call.args[0] for call in self.session.send.call_args_list]
                    self.assertTrue(any("+105 " + job.capitalize() + " XP" in msg for msg in messages))
                    self.assertTrue(any("x3 EXP perk" in msg for msg in messages))

    def test_double_exp_is_double_and_perk_off_returns_to_normal(self):
        with patch.object(village_perks, "xp_multiplier", side_effect=[2.0, 1.0]):
            commands._award_job_action_xp(self.session, "fishing", 40)
            commands._award_job_action_xp(self.session, "fishing", 40)
        self.assertEqual(jobs.get_job_xp(self.player, "fishing"), 120)
        msgs = [call.args[0] for call in self.session.send.call_args_list]
        self.assertIn("+80 Fishing XP", msgs[0])
        self.assertIn("x2 EXP perk", msgs[0])
        self.assertIn("+40 Fishing XP", msgs[1])
        self.assertNotIn("perk", msgs[1].lower())

    def test_zero_and_capped_job_xp_not_falsely_displayed(self):
        self.player.job_levels["fishing"] = jobs.MAX_JOB_LEVEL
        commands._award_job_action_xp(self.session, "fishing", 30)
        commands._award_job_action_xp(self.session, "mining", 0)
        self.assertFalse(any(" XP" in call.args[0] for call in self.session.send.call_args_list))

    def test_level_rewards_follow_xp_message(self):
        commands._award_job_action_xp(self.session, "fishing", jobs.job_xp_for_level(2))
        messages = [call.args[0] for call in self.session.send.call_args_list]
        self.assertIn("+250 Fishing XP", messages[0])
        self.assertTrue(any("level increased to 2" in m for m in messages[1:]))


class AuthenticChakraSteelTests(unittest.TestCase):
    def setUp(self):
        content._register_shared_items()
        self.player = Player("Smith", "Smith", primary_class="bukijutsu", level=75)
        self.player.chakra_nature = "lightning"
        self.player.chakra_nature_revealed = True
        self.player.chakra = self.player.stamina = 500
        self.player.learned_skills.append("Weapon Enchantment")
        self.session = NS(player=self.player, send=Mock())
        self.created = []
        self.addCleanup(self.remove_templates)

    def remove_templates(self):
        for vnum in self.created:
            olc.OBJECT_TEMPLATES.pop(vnum, None)

    def forge(self, name, kind, materials=None, description=None):
        vnum = 998000 + len(self.created)
        template = olc.default_object(vnum, name)
        template["item_type"] = "weapon"
        template["weapon_type"] = kind
        if materials is not None:
            template["craft_materials"] = materials
        if description is not None:
            template["description"] = description
        olc.OBJECT_TEMPLATES[vnum] = template
        self.created.append(vnum)
        return name

    def test_all_weapon_types_accept_real_chakra_steel(self):
        for kind in ("kunai", "sword", "shuriken", "blunt", "polearm", "exotic"):
            with self.subTest(kind=kind):
                self.player.cooldowns.clear()
                name = self.forge(f"Unique Chakra Forged {kind}", kind,
                                  ["chakra steel ingot", "yew log"])
                self.player.equipment["wielded"] = name
                ninja_arts.use_weapon_art(self.session, "weapon enchantment",
                                          ["unique", "chakra", "forged", kind, "lightning"])
                result = self.player.equipment["wielded"]
                self.assertEqual(ninja_arts.element_of(result), "lightning")
                self.assertEqual(ninja_arts.base_item(result), name)
                target = Player("Target", "Target")
                with patch.object(ninja_arts.random, "randint", return_value=1):
                    self.assertEqual(ninja_arts.weapon_hit(self.player, target, 100), 150)
                self.assertIn("paralyzed", target.active_status_effects)

    def test_weapon_name_cannot_fake_chakra_steel(self):
        name = self.forge("A Chakra Steel Legendary Katana", "sword",
                          ["iron ingot", "sturdy oak log"])
        self.player.equipment["wielded"] = name
        chakra = self.player.chakra
        ninja_arts.use_weapon_art(self.session, "weapon enchantment",
                                  ["chakra", "steel", "legendary", "katana", "lightning"])
        self.assertEqual(self.player.equipment["wielded"], name)
        self.assertEqual(self.player.chakra, chakra)
        self.assertIn("Chakra Steel Ingot", self.session.send.call_args.args[0])

    def test_legacy_crafted_weapon_description_is_recognized(self):
        name = "Antique Crafted Spear"
        self.forge(name, "polearm",
                   description=f"A crafted weapon named {name}, forged from yew log and chakra steel ingot.")
        self.assertTrue(ninja_arts.is_chakra_steel_weapon(name))
        name2 = "Cheap Weapon With An Impressive Name"
        self.forge(name2, "exotic",
                   description=f"A crafted weapon named {name2}, forged from iron ingot and oak log.")
        self.assertFalse(ninja_arts.is_chakra_steel_weapon(name2))

    def test_non_sword_elemental_bonus_without_samurai_sabre(self):
        self.player.samurai_sabre_active = True
        name = self.forge("Genuine Chakra Kunai", "kunai",
                          ["chakra steel ingot", "yew log"])
        self.player.equipment["wielded"] = name + " [element:lightning]"
        with patch.object(ninja_arts.random, "randint", return_value=100):
            self.assertEqual(ninja_arts.weapon_hit(self.player, Player("Target", "Target"), 100), 150)


class ChangeLogTests(unittest.TestCase):
    def test_latest_changes_visible_in_game(self):
        entries = dict(changelog.CHANGELOG)
        for version, keyword in (
            ("15.383", "KKGK"), ("15.384", "VNUM 6"),
            ("15.385", "LEVELUP"), ("15.386", "Chakra Steel"),
            ("15.387", "job XP"), ("15.388", "Kamui"),
        ):
            self.assertIn(keyword, entries[version])


if __name__ == "__main__":
    unittest.main()
