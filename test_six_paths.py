"""Awakening eligibility, costs, combat gates and saved mode lifecycle."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_handsigns
import data_jutsu
import leveling
from models import Player
import sage_mode
import six_paths
import storage


class SixPathsTests(unittest.TestCase):
    def player(self, soul="indra", level=75, primary_class="taijutsu"):
        rank = ("kage" if level > 95 else "elite jonin" if level > 80
                else "jonin" if level > 55 else "special jonin" if level > 35
                else "chunin" if level > 15
                else "genin" if level > 10 else "academy student")
        p = Player("Reborn", "Reborn", level=level, primary_class=primary_class,
                   village_rank=rank, reincarnation=soul, chakra=1000, maximum_chakra=1000,
                   stamina=1000, maximum_stamina=1000, room_vnum=1)
        return p

    def session(self, p):
        return NS(player=p, send=Mock(), broadcast_room=Mock(), pending_cast=None,
                  combat_target=None, pvp_target=None)

    def test_unlock_at_75_for_both_lineages_and_all_classes_only_once(self):
        for soul in six_paths.MODE_SKILLS:
            for cls in ("ninjutsu", "genjutsu", "taijutsu", "bukijutsu"):
                p = self.player(soul, 74, cls)
                self.assertEqual(six_paths.sync_skills(p), [])
                p.level = 75
                self.assertEqual(len(six_paths.sync_skills(p)), 3)
                expected = {six_paths.MODE_SKILLS[soul], *six_paths.TECHNIQUES[soul]}
                self.assertEqual(set(p.learned_skills), expected)
                p.skill_proficiencies[six_paths.MODE_SKILLS[soul]] = 60
                with patch.object(storage, "save_player"):
                    leveling.sync_universal_skills(p)
                self.assertEqual(p.skill_proficiencies[six_paths.MODE_SKILLS[soul]], 60)
                self.assertEqual(six_paths.sync_skills(p), [])
        self.assertEqual(six_paths.sync_skills(self.player("", 100)), [])

    def test_level_up_awakes_on_actual_threshold(self):
        p = self.player("ashura", 74)
        p.experience = leveling.cumulative_xp_for_level(74)
        with patch.object(storage, "save_player"):
            messages = leveling.grant_experience(p, leveling.xp_band_for_level(74))
        self.assertEqual(p.level, 75)
        self.assertIn("Six Paths Sage Mode", p.learned_skills)
        self.assertTrue(any("Six Paths chakra awakens" in line for line in messages))

    def test_activation_idle_combat_and_unfunded_stop(self):
        p = self.player()
        s = self.session(p)
        with patch.object(storage, "save_player"):
            six_paths.command(s, ["on"])
            self.assertTrue(six_paths.active(p))
            self.assertEqual(p.chakra, 960)
            six_paths.command(s, ["on"])
            self.assertEqual(p.chakra, 960)
            six_paths.idle_upkeep(s)
            self.assertEqual(p.chakra, 942)
            sage_mode.combat_pulse(s)
            self.assertEqual((p.chakra, p.stamina), (918, 992))
            p.stamina = 7
            sage_mode.combat_pulse(s)
            self.assertFalse(p.six_paths_active)
            self.assertEqual((p.chakra, p.stamina), (918, 7))
            self.assertEqual(sage_mode.outgoing(p, 100), 100)

    def test_bonuses_scale_with_mastery_and_never_stack_with_sage(self):
        p = self.player()
        p.six_paths_active = True
        p.skill_proficiencies["Six Paths Rinnegan"] = 100
        self.assertEqual(sage_mode.outgoing(p, 100), 120)
        self.assertEqual(sage_mode.incoming(p, 100), 85)
        self.assertEqual(sage_mode.accuracy(p), 10)
        p.sage_active_contract = "slug"
        self.assertFalse(six_paths.active(p))
        self.assertEqual(six_paths.bonuses(p), (0, 0, 0))
        p.six_paths_active = False
        with patch.object(storage, "save_player"):
            six_paths.command(self.session(p), ["on"])
        self.assertFalse(p.six_paths_active)
        self.assertEqual(p.chakra, 1000)

    def test_lineage_active_level_and_copy_gates(self):
        p = self.player()
        six_paths.sync_skills(p)
        push = data_jutsu.JUTSU["almighty push"]
        self.assertFalse(combat._can_use_jutsu(p, push, "almighty push"))
        p.six_paths_active = True
        self.assertTrue(combat._can_use_jutsu(p, push, "almighty push"))
        p.level = 74
        self.assertFalse(combat._can_use_jutsu(p, push, "almighty push"))
        p.level = 75
        p.reincarnation = "ashura"
        p.copied_jutsu_key = "almighty push"
        self.assertFalse(combat._can_use_jutsu(p, push, "almighty push"))
        p.reincarnation = ""
        self.assertFalse(combat._can_use_jutsu(p, push, "almighty push"))

    def test_each_technique_really_hits_mobs_and_players_and_has_cost_and_cooldown(self):
        for soul, names in six_paths.TECHNIQUES.items():
            for name in names:
                for pvp in (False, True):
                    with self.subTest(soul=soul, name=name, pvp=pvp):
                        p = self.player(soul)
                        six_paths.sync_skills(p)
                        p.six_paths_active = True
                        p.skill_proficiencies[name] = 100
                        s = self.session(p)
                        key = name.lower()
                        if key == "six paths vital surge":
                            continue
                        jutsu = data_jutsu.JUTSU[key]
                        self.assertFalse(data_handsigns.has_handsigns(jutsu))
                        victim = self.player("", 75) if pvp else combat.Mob(1, 100, "enemy", 75, 100000, 100000, 1, 0, 0)
                        victim.health = 100000
                        rolls = iter([1, 100] if pvp else [])
                        with patch.object(combat.random, "randint", side_effect=lambda lo, hi: next(rolls, lo)), \
                             patch.object(combat, "_jutsu_damage_bonus", return_value=0):
                            if pvp:
                                combat.use_jutsu_on_player(s, key, self.session(victim))
                            else:
                                combat.use_jutsu(s, key, victim)
                        self.assertLess(victim.health, 100000)
                        self.assertEqual(p.chakra, 1000 - jutsu["chakra_cost"])
                        self.assertEqual(p.stamina, 1000 - jutsu["stamina_cost"])
                        self.assertGreater(p.cooldowns[key], 0)
                        self.assertIn(jutsu["effect"], victim.active_status_effects)
                        before = victim.health
                        with patch.object(combat.random, "randint", return_value=1):
                            if pvp:
                                combat.use_jutsu_on_player(s, key, self.session(victim))
                            else:
                                combat.use_jutsu(s, key, victim)
                        self.assertEqual(victim.health, before)

    def test_save_reload_preserves_unlocks_but_releases_mode(self):
        p = self.player("ashura")
        six_paths.sync_skills(p)
        p.six_paths_active = True
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(storage, "DATA_DIR", tmp), \
             patch.object(storage, "ACCOUNTS_DIR", os.path.join(tmp, "accounts")), \
             patch.object(storage, "PLAYERS_DIR", os.path.join(tmp, "players")):
            storage.save_player(p)
            loaded = storage.load_player(p.name)
        self.assertEqual(loaded.reincarnation, "ashura")
        self.assertEqual(loaded.learned_skills, p.learned_skills)
        self.assertEqual(loaded.skill_proficiencies, p.skill_proficiencies)
        self.assertFalse(loaded.six_paths_active)
        self.assertEqual(loaded.maximum_chakra, p.maximum_chakra)

    def test_mode_command_dispatch_and_death_invalidate_power(self):
        p = self.player()
        s = self.session(p)
        with patch.object(storage, "save_player"):
            commands.cmd_use_jutsu(s, "six paths rinnegan", [])
            self.assertTrue(p.six_paths_active)
            p.health = 0
            six_paths.combat_pulse(s)
            self.assertFalse(p.six_paths_active)


if __name__ == "__main__":
    unittest.main()
