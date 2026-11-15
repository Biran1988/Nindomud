"""Kai ordinary-genjutsu dispel and level-based staff consumable balance."""
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import combat
import consumables
import data_jutsu
import item_balance
import jutsu_scroll_catalog
import olc
import status_effects
import storage
from models import Player


class KaiAndHealingBalanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st=patch.object(storage, "DATA_DIR", tmp.name)
        st.start(); self.addCleanup(st.stop)
        self.templates=patch.dict(olc.OBJECT_TEMPLATES, {}, clear=True)
        self.templates.start();self.addCleanup(self.templates.stop)
        self.audit=patch.object(olc, "_log")
        self.audit.start();self.addCleanup(self.audit.stop)
        self.player=Player("KaiTester","KaiTester",level=50)
        self.player.chakra=5000
        self.player.maximum_chakra=5000
        self.player.maximum_health=10000
        self.player.maximum_stamina=10000
        self.player.health=self.player.stamina=0
        self.session=NS(player=self.player,account=NS(staff_level="implementor"),
                        send=Mock(),pending_cast=None,combat_target=None,pvp_target=None)
        self.player.learned_skills.append("Kai")

    def test_kai_class_unlock_and_append_only_scroll_vnum(self):
        self.assertEqual(data_jutsu.JUTSU["kai"]["level_requirement"],15)
        for school in ("ninjutsu","taijutsu","genjutsu","bukijutsu"):
            self.assertIn("kai",data_jutsu.jutsu_for_class_at_level(school,15))
        self.assertEqual(jutsu_scroll_catalog.vnum_for("kai"),31760)
        self.assertEqual(jutsu_scroll_catalog.vnum_for("celestial nova sphere"),31744)

    def test_kai_cleanses_only_ordinary_genjutsu_and_illusion_walk(self):
        import kai
        with patch.object(combat,"_can_use_jutsu",return_value=True),patch.object(combat,"grow_skill_from_usage"):
            status_effects.apply_effect(self.player.active_status_effects,"asleep",
                                         source="nehan shouja",genjutsu=True)
            status_effects.apply_effect(self.player.active_status_effects,"confused",
                                         source="phantom floor maze",genjutsu=True)
            status_effects.apply_effect(self.player.active_status_effects,"stunned",
                                         source="physical attack")
            status_effects.apply_effect(self.player.active_status_effects,"poisoned",
                                         source="poison")
            self.player.illusion_walk_caster="Other"
            self.player.illusion_walk_real_room_vnum=41
            self.player.illusion_walk_range=5
            self.player.illusion_walk_steps_taken=2
            with patch.object(commands,"cmd_look"):
                commands.cmd_use_jutsu(self.session,"kai",[])
        self.assertFalse(self.player.active_status_effects["stunned"].get("genjutsu",False))
        self.assertEqual(set(self.player.active_status_effects),{"stunned","poisoned"})
        self.assertIsNone(self.player.illusion_walk_caster)
        self.assertIsNone(self.player.illusion_walk_real_room_vnum)
        self.assertEqual(self.player.illusion_walk_range,0)
        self.assertEqual(self.player.illusion_walk_steps_taken,0)

    def test_kai_no_cost_when_no_illusion_and_non_genjutsu_action_lock(self):
        import kai
        with patch.object(combat,"_can_use_jutsu",return_value=True):
            old=self.player.chakra
            kai.cast(self.session,[])
            self.assertEqual(old,self.player.chakra)
            status_effects.apply_effect(self.player.active_status_effects,"stunned",source="physical")
            status_effects.apply_effect(self.player.active_status_effects,"asleep",
                                         source="nehan shouja",genjutsu=True)
            kai.cast(self.session,[])
            self.assertIn("asleep",self.player.active_status_effects)
            self.assertEqual(old,self.player.chakra)
            status_effects.dispel_genjutsu_effects(self.player.active_status_effects)
            self.assertIn("stunned",self.player.active_status_effects)

    def make_item(self,vnum,name,category,level):
        olc.cmd_ocreate(self.session,[str(vnum),*name.split()])
        olc.cmd_oset(self.session,[str(vnum),"itemtype",category])
        olc.cmd_oset(self.session,[str(vnum),"level",str(level)])
        proto=olc.OBJECT_TEMPLATES[vnum]
        self.assertTrue(item_balance.active(proto))
        return proto

    def test_staff_medical_level_auto_and_manual_override(self):
        proto=self.make_item(997001,"A Trial Potion","medical",100)
        expected=item_balance.scaled(100,"healing")
        self.assertEqual(item_balance.effective_recovery(proto,"healing"),expected)
        self.player.inventory=["A Trial Potion"]
        with patch.object(consumables.time,"time",return_value=1000):
            consumables.consume(self.session,"use","trial potion")
        self.assertEqual(self.player.medical_healing[-1]["amount"],expected)
        self.assertEqual(self.player.medical_healing[-1]["resources"],["health"])
        self.assertEqual(consumables.tick_medical_healing(self.player,now=1030)["health"],expected)
        olc.cmd_oset(self.session,["997001","heal","91"])
        self.assertEqual(item_balance.effective_recovery(proto,"healing"),91)
        olc.cmd_oset(self.session,["997001","heal","0"])
        self.assertEqual(item_balance.effective_recovery(proto,"healing"),expected)

    def test_food_level_recovery_and_live_tuning(self):
        proto=self.make_item(997002,"A Test Rice Ball","food",125)
        base=item_balance.scaled(125,"food")
        self.player.inventory=["A Test Rice Ball"]
        consumables.consume(self.session,"eat","test rice ball")
        self.assertEqual(self.player.stamina,base)
        item_balance.cmd_itemscale(self.session,["food","200"])
        self.assertEqual(item_balance.effective_recovery(proto,"food"),base*2)
        olc.cmd_oset(self.session,["997002","healflags","health"])
        self.player.inventory=["A Test Rice Ball"]
        consumables.consume(self.session,"eat","test rice ball")
        self.assertEqual(self.player.health,base*2)
        self.assertEqual(self.player.stamina,base)
        olc.cmd_oset(self.session,["997002","heal","19"])
        self.assertEqual(item_balance.effective_recovery(proto,"food"),19)

    def test_old_consumables_not_mutated_and_existing_food_exception(self):
        standard=olc.default_object(997003,"A Leviathan Fillet")
        standard.update(item_type="food",level=250)
        olc.OBJECT_TEMPLATES[997003]=standard
        self.assertFalse(item_balance.active(standard))
        self.player.inventory=["A Leviathan Fillet"]
        consumables.consume(self.session,"eat","leviathan fillet")
        self.assertEqual(self.player.stamina,5000)
        self.assertFalse(standard["extra_flags"])
        self.assertEqual(standard["heal_amount"],0)


if __name__=="__main__":
    unittest.main()
