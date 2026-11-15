"""Sanctuary, Elemental Shield, upgraded barriers, upkeep, and scroll safety."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import combat
import commands
import data_jutsu
import general_skills
import help_system
import jutsu_balance
import jutsu_scroll_catalog
import leveling
import skill_training
import status_effects
from models import Player


class DefensiveJutsuTests(unittest.TestCase):
    def make(self, level=160, element="lightning", klass="taijutsu"):
        player = Player("DefenseStudent", "DefenseStudent", primary_class=klass, level=level)
        player.chakra_nature = element
        player.chakra = player.maximum_chakra = 50000
        player.stamina = player.maximum_stamina = 50000
        player.health = player.maximum_health = 50000
        player.room_vnum = 3000
        player.practice_gate_enabled = True
        out = []
        session = NS(player=player, send=out.append, pending_cast=None,
                     combat_target=None, pvp_target=None)
        with patch('storage.save_player'):
            leveling.sync_universal_skills(player)
        for name in ('Barrier','Reinforced Barrier','Fortress Barrier',
                     'Sanctuary','Elemental Shield'):
            if name in player.learned_skills:
                player.skill_proficiencies[name] = 60
                skill_training.mark_practiced(player,name)
        return player, session, out

    def test_all_classes_get_level_gated_skills_and_no_premature_unlock(self):
        levels = {'reinforced barrier':70,'sanctuary':90,'elemental shield':100,
                  'fortress barrier':150}
        for klass in ('ninjutsu','genjutsu','taijutsu','bukijutsu'):
            for key,level in levels.items():
                with self.subTest(klass=klass,key=key):
                    self.assertEqual(data_jutsu.JUTSU[key]['level_requirement'], level)
                    self.assertIn(key,data_jutsu.jutsu_for_class_at_level(klass,level))
                    self.assertNotIn(key,data_jutsu.all_unlocked_for_class(klass,level-1))
            p=Player('Returner','Returner',primary_class=klass,level=160)
            with patch('storage.save_player'):
                leveling.sync_universal_skills(p)
            for key in levels:
                self.assertIn(data_jutsu.JUTSU[key]['display_name'],p.learned_skills)

    def test_sanctuary_reduces_half_stays_on_move_and_survives_save(self):
        player, session, out = self.make(level=95)
        with patch.object(combat, 'grow_skill_from_usage'),patch.object(general_skills.time,'time',return_value=1000.0):
            commands.cmd_use_jutsu(session,'sanctuary',['on'])
        self.assertIn('sanctuary',player.active_status_effects)
        self.assertEqual(status_effects.reduce_incoming_damage(player.active_status_effects,200),100)
        player.room_vnum=3100
        self.assertIn('sanctuary',player.active_status_effects)
        restored=Player.from_dict(player.to_dict())
        self.assertIn('sanctuary',restored.active_status_effects)
        self.assertEqual(status_effects.reduce_incoming_damage(restored.active_status_effects,200),100)
        commands.cmd_use_jutsu(session,'sanctuary',['off'])
        self.assertNotIn('sanctuary',player.active_status_effects)
        self.assertEqual(status_effects.reduce_incoming_damage(player.active_status_effects,200),200)

    def test_sanctuary_off_is_possible_on_cooldown_and_gate_blocks_early_use(self):
        p,s,out = self.make(level=89)
        commands.cmd_use_jutsu(s,'sanctuary',['on'])
        self.assertNotIn('sanctuary',p.active_status_effects)
        p.level=90
        p.learned_skills.append('Sanctuary')
        p.skill_proficiencies['Sanctuary']=10
        skill_training.mark_practiced(p,'Sanctuary')
        with patch.object(combat,'grow_skill_from_usage'):
            commands.cmd_use_jutsu(s,'sanctuary',['on'])
        self.assertIn('sanctuary',p.active_status_effects)
        commands.cmd_use_jutsu(s,'sanctuary',['off'])
        self.assertNotIn('sanctuary',p.active_status_effects)
        commands.cmd_use_jutsu(s,'sanctuary',['on'])
        self.assertNotIn('sanctuary',p.active_status_effects)

    def test_elemental_shield_gives_separate_attack_benefit_and_is_universal(self):
        p,s,_=self.make(level=100,element='lightning',klass='genjutsu')
        chidori=data_jutsu.JUTSU['chidori']
        fire=data_jutsu.JUTSU['fireball jutsu']
        base_lightning=jutsu_balance.boosted_damage(p,chidori,500)
        base_fire=jutsu_balance.boosted_damage(p,fire,500)
        with patch.object(combat,'grow_skill_from_usage'):
            commands.cmd_use_jutsu(s,'elemental shield',['on'])
        self.assertIn('elemental_shield',p.active_status_effects)
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,200),140)
        self.assertEqual(general_skills.elemental_accuracy(p),5)
        self.assertGreater(jutsu_balance.boosted_damage(p,chidori,500),base_lightning)
        self.assertEqual(jutsu_balance.boosted_damage(p,fire,500),base_fire)
        p.room_vnum=3200
        self.assertIn('elemental_shield',p.active_status_effects)
        commands.cmd_use_jutsu(s,'elemental shield',['off'])
        self.assertNotIn('elemental_shield',p.active_status_effects)
        self.assertEqual(general_skills.elemental_accuracy(p),0)

    def test_upkeep_occurs_in_idle_ticks_and_turns_off_when_out_of_chakra(self):
        p,s,_=self.make(level=100)
        with patch.object(combat,'grow_skill_from_usage'), patch.object(general_skills.time,'time',return_value=1000):
            commands.cmd_use_jutsu(s,'sanctuary',['on'])
            commands.cmd_use_jutsu(s,'elemental shield',['on'])
        initial=p.chakra
        with patch.object(general_skills.time,'time',return_value=1004):
            general_skills.defense_upkeep(s)
        self.assertEqual(p.chakra,initial)
        with patch.object(general_skills.time,'time',return_value=1005):
            general_skills.defense_upkeep(s)
        self.assertEqual(p.chakra,initial-11)
        with patch.object(general_skills.time,'time',return_value=1006):
            general_skills.defense_upkeep(s)
        self.assertEqual(p.chakra,initial-11)  # not charged per pulse
        p.chakra=4
        with patch.object(general_skills.time,'time',return_value=1010):
            general_skills.defense_upkeep(s)
        self.assertNotIn('sanctuary',p.active_status_effects)
        self.assertNotIn('elemental_shield',p.active_status_effects)
        self.assertEqual(p.chakra,4)

    def test_barrier_tiers_room_bound_never_stack_or_downgrade(self):
        p,s,out=self.make()
        with patch.object(combat,'grow_skill_from_usage'):
            commands.cmd_use_jutsu(s,'barrier',[])
            self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,200),150)
            commands.cmd_use_jutsu(s,'reinforced barrier',[])
            self.assertNotIn('barrier',p.active_status_effects)
            self.assertIn('reinforced_barrier',p.active_status_effects)
            self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,200),130)
            commands.cmd_use_jutsu(s,'fortress barrier',[])
            self.assertNotIn('reinforced_barrier',p.active_status_effects)
            self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,200),110)
            remaining=p.chakra
            commands.cmd_use_jutsu(s,'barrier',[])
            self.assertEqual(p.chakra,remaining)
            self.assertIn('fortress_barrier',p.active_status_effects)
        p.room_vnum+=1
        for effect in ('barrier','reinforced_barrier','fortress_barrier'):
            self.assertNotIn(effect,p.active_status_effects)
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,200),200)

    def test_strongest_effect_wins_in_pvp_mobs_and_dot(self):
        p,s,_=self.make()
        with patch.object(combat,'grow_skill_from_usage'):
            commands.cmd_use_jutsu(s,'fortress barrier',[])
            commands.cmd_use_jutsu(s,'sanctuary',[])
            commands.cmd_use_jutsu(s,'elemental shield',[])
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,600),300)
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,9),4)
        p.room_vnum=3500
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,600),300)
        p.active_status_effects.pop('sanctuary',None)
        self.assertEqual(status_effects.reduce_incoming_damage(p.active_status_effects,600),420)

    def test_scroll_vnums_unchanged_and_new_techniques_appended(self):
        old={9810:31501,9812:31502,9771:31550,9750:31606,9821:31537}
        self.assertEqual(jutsu_scroll_catalog.legacy_vnums(),old)
        self.assertEqual(len(jutsu_scroll_catalog.entries()), 243 + 17)
        self.assertEqual(len(jutsu_scroll_catalog.BASE_SCROLL_KEYS),235)
        self.assertEqual({key for _,key,_ in jutsu_scroll_catalog.entries()[235:239]},
                         {'reinforced barrier','fortress barrier','sanctuary','elemental shield'})
        self.assertEqual([key for _, key, _ in jutsu_scroll_catalog.entries()[239:243]],
                         ['second attack', 'third attack', 'fourth attack', 'fifth attack'])
        for key in ('reinforced barrier','fortress barrier','sanctuary','elemental shield'):
            self.assertTrue(31736 <= jutsu_scroll_catalog.vnum_for(key) <=31739)
        # Existing assigned scrolls are never shifted by later technique additions.
        self.assertEqual(jutsu_scroll_catalog.vnum_for('celestial nova sphere'), 31744)
        self.assertEqual(jutsu_scroll_catalog.vnum_for('dragonfire pulse'), 31745)
        self.assertEqual(len(jutsu_scroll_catalog.entries()[243:259]), 16)
        self.assertEqual(jutsu_scroll_catalog.vnum_for('kai'), 31760)

    def test_help_matches_real_values(self):
        lookup={x['primary_keyword']:x['body'] for x in help_system.DEFAULT_HELP_ENTRIES}
        for key in ('barrier','reinforced barrier','fortress barrier','sanctuary','elemental shield'):
            self.assertIn(key,lookup)
        self.assertIn('50%',lookup['sanctuary'])
        self.assertIn('30%',lookup['elemental shield'])
        self.assertIn('45%',lookup['fortress barrier'])

if __name__=='__main__':unittest.main()
