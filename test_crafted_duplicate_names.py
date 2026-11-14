"""Same-name forged gear keeps separate object identity and persistent behavior."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import commands
import crafted_identity
import crafted_provenance
import data_weapons
import equipment_durability
import gem_inlays
import inventory
import item_types
import ninja_arts
import olc
from models import Player
from session import _terminal_safe_text


class SameNameCraftTests(unittest.TestCase):
    def setUp(self):
        self.before = set(olc.OBJECT_TEMPLATES)
        self.previous_next = commands._NEXT_CRAFTED_ITEM_VNUM
        commands._NEXT_CRAFTED_ITEM_VNUM = 825000
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for vnum in set(olc.OBJECT_TEMPLATES) - self.before:
            olc.OBJECT_TEMPLATES.pop(vnum, None)
        commands._NEXT_CRAFTED_ITEM_VNUM = self.previous_next

    def make_session(self, name, *, class_name='bukijutsu', ip='198.51.100.12'):
        player = Player(name, name, primary_class=class_name, level=250, stamina=300)
        sent = []
        session = NS(player=player, connection_ip=ip, send=sent.append,
                     is_busy=lambda: False, account=NS(staff_level='player'),
                     active_sessions=lambda: [])
        session.enter_single_line = lambda _prompt, cb: cb('iron')
        session.start_timed_action = lambda _kind, _secs, cb: cb()
        return session, sent

    def forge(self, session, kind='sword', metal='iron', name='Shared Shadow Blade'):
        ingredient = {'iron': 'an iron ingot', 'steel': 'a steel ingot',
                      'chakra steel': 'a chakra steel ingot'}[metal]
        session.player.inventory.extend([ingredient, ingredient])
        session.enter_single_line = lambda _prompt, cb: cb(metal)
        with (patch('world_autosave.mark_dirty'),
              patch('jobs.try_deduct_action_stamina', return_value=True)):
            commands.cmd_craft(session, ['weapon', kind, *name.split()])
        gear = [x for x in session.player.inventory
                if crafted_identity.display(x) == name]
        return gear[-1]

    def test_two_same_named_items_have_different_vnums_stats_and_weapon_types(self):
        session, messages = self.make_session('Forger')
        first = self.forge(session, kind='sword', metal='iron')
        second = self.forge(session, kind='exotic', metal='chakra steel')
        v1, v2 = crafted_identity.vnum(first), crafted_identity.vnum(second)
        self.assertNotEqual(v1, v2)
        self.assertEqual(crafted_identity.display(first), crafted_identity.display(second))
        self.assertEqual(olc.OBJECT_TEMPLATES[v1]['short_desc'], 'Shared Shadow Blade')
        self.assertEqual(olc.OBJECT_TEMPLATES[v2]['short_desc'], 'Shared Shadow Blade')
        self.assertIs(commands._find_object_prototype_by_name(first), olc.OBJECT_TEMPLATES[v1])
        self.assertIs(commands._find_object_prototype_by_name(second), olc.OBJECT_TEMPLATES[v2])
        self.assertEqual(commands.find_indexed_item('2.shadow blade', session.player.inventory), second)
        self.assertEqual(data_weapons.weapon_type_for_item(first), 'sword')
        self.assertEqual(data_weapons.weapon_type_for_item(second), 'exotic')
        self.assertEqual(commands._find_object_vnum_by_name(first), v1)
        self.assertEqual(commands._find_object_vnum_by_name(second), v2)
        self.assertEqual(item_types.classify_item(first), 'weapon')
        self.assertEqual(item_types.classify_item(second), 'weapon')
        self.assertEqual(equipment_durability.state(olc.OBJECT_TEMPLATES[v1]), (2500, 2500))
        self.assertEqual(equipment_durability.state(olc.OBJECT_TEMPLATES[v2]), (10000, 10000))
        self.assertFalse(any('forged-vnum:' in line for line in messages))
        self.assertEqual(inventory.slot_counts([first, second]), {first: 1, second: 1})

    def test_enchantment_and_gem_resolve_exact_vnum_without_bleeding(self):
        session, _ = self.make_session('Forger')
        iron = self.forge(session, metal='iron')
        chakra = self.forge(session, metal='chakra steel')
        self.assertFalse(ninja_arts.is_chakra_steel_weapon(iron))
        self.assertTrue(ninja_arts.is_chakra_steel_weapon(chakra))
        other = chakra + ' [element:fire]'
        self.assertIs(commands._find_object_prototype_by_name(other), olc.OBJECT_TEMPLATES[crafted_identity.vnum(chakra)])
        a, b = olc.OBJECT_TEMPLATES[crafted_identity.vnum(iron)], olc.OBJECT_TEMPLATES[crafted_identity.vnum(chakra)]
        b['gem_inlay'] = 'ruby'
        self.assertIs(gem_inlays.forged_prototype(iron), a)
        self.assertIs(gem_inlays.forged_prototype(chakra), b)
        session.player.equipment['wielded'] = iron
        self.assertEqual(gem_inlays.equipment_flat_bonus(session.player), 0)
        session.player.equipment['wielded'] = chakra
        self.assertEqual(gem_inlays.equipment_flat_bonus(session.player), 10)
        self.assertEqual(gem_inlays.elemental_jutsu_multiplier(session.player, 'fire'), 1.15)
        b['durability'] -= 1
        self.assertEqual(equipment_durability.state(a), (2500, 2500))
        self.assertEqual(equipment_durability.state(b), (9999, 10000))

    def test_vnum_survives_player_save_and_different_creators_remain_protected(self):
        first, _ = self.make_session('MakerA', ip='192.0.2.20')
        second, _ = self.make_session('MakerB', ip='192.0.2.30')
        first_item = self.forge(first)
        second_item = self.forge(second)
        copy = Player.from_dict(first.player.to_dict())
        self.assertEqual(copy.inventory, first.player.inventory)
        self.assertEqual(crafted_identity.vnum(copy.inventory[0]), crafted_identity.vnum(first_item))
        # Only *same-IP* alternate characters are blocked, not a different
        # household. The prototype selected must still be the right maker.
        self.assertFalse(crafted_provenance.denied(first_item, second.player, session=second))
        self.assertFalse(crafted_provenance.denied(second_item, first.player, session=first))
        alt_a, _ = self.make_session('AltA', ip='192.0.2.20')
        alt_b, _ = self.make_session('AltB', ip='192.0.2.30')
        self.assertTrue(crafted_provenance.denied(first_item, alt_a.player, session=alt_a))
        self.assertFalse(crafted_provenance.denied(first_item, alt_b.player, session=alt_b))
        self.assertTrue(crafted_provenance.denied(second_item, alt_b.player, session=alt_b))
        self.assertFalse(crafted_provenance.denied(second_item, alt_a.player, session=alt_a))
        self.assertFalse(crafted_provenance.denied(first_item, first.player, session=first))
        self.assertFalse(crafted_provenance.denied(second_item, second.player, session=second))

    def test_wield_swaps_two_distinct_same_name_weapons_and_inventory_numbers_them(self):
        session, output = self.make_session('Wielder')
        first = self.forge(session, kind='sword', metal='iron')
        second = self.forge(session, kind='exotic', metal='chakra steel')
        with (patch('commands._fire_item_trigger'),
              patch('room_actions.emit')):
            commands.cmd_wield(session, ['shadow', 'blade'])
            self.assertEqual(session.player.equipment['wielded'], first)
            commands.cmd_wield(session, ['shadow', 'blade'])
            self.assertEqual(session.player.equipment['wielded'], second)
        self.assertIn(first, session.player.inventory)
        self.assertNotIn(second, session.player.inventory)
        session.player.inventory.append(second)
        commands.cmd_inventory(session, [])
        self.assertIn('1. Shared Shadow Blade', output[-1])
        self.assertIn('2. Shared Shadow Blade', output[-1])

    def test_session_hides_internal_vnum_reference_in_client_output(self):
        from session import Session, State
        sent=[]
        s=Session.__new__(Session)
        s.send_raw=sent.append
        s.color_enabled=False
        s.state=State.NAME
        s.send('You equip '+crafted_identity.encode('Shared Shadow Blade', 825000)+'.')
        self.assertEqual(sent[-1], 'You equip Shared Shadow Blade.\r\n')

    def test_legacy_name_only_save_stays_tied_to_original_when_name_reused(self):
        original_vnum=825499
        original = {'short_desc': 'Old Famous Sword', 'item_type': 'weapon',
                    'weapon_type': 'sword', 'craft_materials': ['iron ingot']*2,
                    'stat_bonuses': {'hitroll': 5}}
        olc.OBJECT_TEMPLATES[original_vnum]=original
        session, _ = self.make_session('NewMaker')
        item = self.forge(session, name='Old Famous Sword')
        self.assertEqual(commands._find_object_vnum_by_name('Old Famous Sword'), original_vnum)
        self.assertEqual(commands._find_object_vnum_by_name(item), crafted_identity.vnum(item))
        self.assertTrue(original['legacy_name_owner'])


if __name__=='__main__':
    unittest.main()
