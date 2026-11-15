"""Live merchant flags and opt-in, persisted item-level balance integration."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import commands
import data_shops
import data_weapons
import item_balance
import item_types
import olc
import pawnshops
import shop_flags
import storage
import tool_durability
from models import Player


class ShopAndItemScaleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.mock_data = patch.object(storage, 'DATA_DIR', self.temp.name)
        self.mock_data.start()
        self.addCleanup(self.mock_data.stop)
        self.player = Player('FlagBuilder', 'FlagBuilder', room_vnum=992310)
        self.admin = SimpleNamespace(player=self.player,
                                     account=SimpleNamespace(staff_level='implementor'),
                                     send=Mock())
        self.mob_id = 992311
        self.mob = combat.default_template(self.mob_id, 'a merchant')
        self.mob['act_flags'] = ['Npc', 'Sentinel']
        self.item_id = 992312
        self.item = olc.default_object(self.item_id, 'A Test Weapon')
        self.item.update(item_type='weapon', weapon_type='sword', wear_loc='wielded', level=100)
        self.mobs = patch.dict(combat.MOB_TEMPLATES, {self.mob_id:self.mob})
        self.mobs.start()
        self.addCleanup(self.mobs.stop)
        self.items = patch.dict(olc.OBJECT_TEMPLATES, {self.item_id:self.item})
        self.items.start()
        self.addCleanup(self.items.stop)
        self.logging = patch.object(olc, '_log')
        self.logging.start()
        self.addCleanup(self.logging.stop)
        self.instance = SimpleNamespace(name='a merchant', template_vnum=self.mob_id,
                                        player_shop_owner=None, room_vnum=self.player.room_vnum)

    def mset(self, *args):
        olc.cmd_mset(self.admin, [str(self.mob_id), *args])

    def oset(self, *args):
        olc.cmd_oset(self.admin, [str(self.item_id), *args])

    def test_all_specialties_work_as_flags_and_only_one_active(self):
        for kind, flag in shop_flags.SHOP_FLAGS.items():
            with self.subTest(kind=kind):
                self.mset('flags', flag)
                self.assertTrue(combat.is_shopkeeper(self.instance))
                self.assertEqual(shop_flags.specialty_from_flags(self.mob), kind)
                self.assertIn('Shopkeeper', self.mob['act_flags'])
                self.assertEqual(len([f for f in self.mob['act_flags']
                                      if shop_flags.specialty_for_flag(f) in shop_flags.SHOP_FLAGS]), 1)
                self.assertEqual(combat.mob_shop_buys_categories(self.instance),
                                 sorted(data_shops.SHOP_TYPES[kind]['allowed_sell_categories'] or []))
        self.mset('flags', '-ShopPawnshop')
        self.assertEqual(shop_flags.specialty_from_flags(self.mob), 'general')
        self.assertTrue(combat.is_shopkeeper(self.instance))
        self.mset('flags', '-Shopkeeper')
        self.assertFalse(combat.is_shopkeeper(self.instance))

    def test_flags_only_and_legacy_editor_commands_are_rejected(self):
        self.mob['shopkeeper'] = False
        self.mob['shop_type'] = 'pawnshop'
        self.mob['act_flags'] = ['Npc', 'ShopMining']
        self.assertTrue(combat.is_shopkeeper(self.instance))
        self.assertEqual(shop_flags.specialty_from_flags(self.mob), 'mining')
        self.mset('shoptype', 'pawnshop')
        self.assertNotIn('ShopPawnshop', self.mob['act_flags'])
        self.assertIn('FLAGS', self.admin.send.call_args.args[0])
        self.mset('shopkeeper', 'off')
        self.assertTrue(combat.is_shopkeeper(self.instance))
        self.assertIn('FLAGS', self.admin.send.call_args.args[0])
        self.mset('flags', 'ShopPawnshop')
        self.assertTrue(pawnshops.is_pawnshop(self.instance))
        self.assertNotIn('shop_type', self.mob)
        self.assertNotIn('shopkeeper', self.mob)
        self.mset('flags', '-Shopkeeper')
        self.assertFalse(combat.is_shopkeeper(self.instance))
        self.mset('flags', 'FoodShop')
        self.assertEqual(shop_flags.specialty_from_flags(self.mob), 'food')

    def test_legacy_templates_upgrade_once_without_reactivating(self):
        legacy = {'act_flags': ['Npc'], 'shopkeeper': True,
                  'shop_type': 'pawnshop', 'shop_items': [777]}
        self.assertTrue(shop_flags.upgrade_legacy(legacy))
        self.assertTrue(shop_flags.is_shopkeeper_template(legacy))
        self.assertEqual(shop_flags.specialty_from_flags(legacy), 'pawnshop')
        self.assertEqual(legacy['shop_items'], [777])
        self.assertNotIn('shop_type', legacy)
        shop_flags.disable_shopkeeper(legacy)
        self.assertFalse(shop_flags.is_shopkeeper_template(legacy))
        self.assertFalse(shop_flags.upgrade_legacy(legacy))
        stale = {'act_flags': ['Npc', 'ShopMining'],
                 'shopkeeper': True, 'shop_type': 'pawnshop'}
        shop_flags.upgrade_legacy(stale)
        self.assertEqual(shop_flags.specialty_from_flags(stale), 'mining')
        self.assertNotIn('shop_type', stale)
        self.assertNotIn('shopkeeper', stale)

    def test_specialty_flag_overrides_stale_categories_and_mstat(self):
        self.mset('flags', 'ShopFood')
        # An imported stale category must never override the live flag.
        self.mob['shop_buys_categories'] = ['weapon']
        self.assertEqual(combat.mob_shop_buys_categories(self.instance), ['food'])
        self.assertTrue(commands._npc_shop_accepts(self.instance, 'A Carrot', 'food'))
        self.assertFalse(commands._npc_shop_accepts(self.instance, 'A Steel Sword', 'weapon'))
        olc.cmd_mstat(self.admin, [str(self.mob_id)])
        display = self.admin.send.call_args.args[0]
        self.assertIn('Merchant flag:', display)
        self.assertIn('ShopFood', display)
        self.assertIn('Buys:&x food', display)

    def test_pawnshop_buy_and_sale_rules_see_flag_immediately(self):
        self.mset('flags', 'ShopPawnshop')
        self.assertEqual(commands._npc_shop_sale_multiplier(self.instance), .5)
        self.assertTrue(commands._npc_shop_accepts(self.instance, 'A Steel Sword', 'weapon'))
        self.assertTrue(pawnshops.is_pawnshop(self.instance))
        self.mset('flags', 'ShopMining')
        self.assertFalse(pawnshops.is_pawnshop(self.instance))
        self.assertTrue(commands._npc_shop_accepts(self.instance, 'Iron Ore', 'ore'))
        self.assertFalse(commands._npc_shop_accepts(self.instance, 'A Steel Sword', 'weapon'))
        self.assertEqual(commands._npc_shop_sale_multiplier(self.instance), 1.5)

    def test_flag_toggle_preserves_other_npc_flags(self):
        self.mset('flags', 'ShopLumberjack')
        self.assertIn('Sentinel', self.mob['act_flags'])
        self.mset('flags', '-ShopLumberjack')
        self.assertIn('Sentinel', self.mob['act_flags'])
        self.assertEqual(shop_flags.specialty_from_flags(self.mob), 'general')
        self.mset('flags', '-Sentinel')
        self.assertNotIn('Sentinel', self.mob['act_flags'])

    def test_item_flag_is_opt_in_and_weapon_damage_changes_live(self):
        old = data_weapons.item_base_damage(self.item)
        self.assertFalse(item_balance.active(self.item))
        self.oset('flags', 'AutoBalance')
        self.assertTrue(item_balance.active(self.item))
        base = data_weapons.item_base_damage(self.item)
        self.assertGreater(base, old)
        item_balance.cmd_itemscale(self.admin, ['damage', '200'])
        self.assertEqual(data_weapons.item_base_damage(self.item), item_balance.scaled(100,'damage'))
        self.item['damage'] = 19
        self.assertEqual(data_weapons.item_base_damage(self.item), 19)
        self.item['damage'] = None
        self.oset('flags', '-AutoBalance')
        self.assertEqual(data_weapons.item_base_damage(self.item), old)

    def test_itemscale_preview_shift_reset_persist_and_permissions(self):
        item_balance.cmd_itemscale(self.admin, ['armor', '125'])
        item_balance.cmd_itemscale(self.admin, ['armor', '+15'])
        self.assertEqual(item_balance.settings()['armor_percent'], 140)
        item_balance.cmd_itemscale(self.admin, ['armor', '-20'])
        self.assertEqual(item_balance.settings()['armor_percent'], 120)
        path = os.path.join(self.temp.name, 'item_balance.json')
        self.assertTrue(os.path.isfile(path))
        item_balance._cached_settings = None
        self.assertEqual(item_balance.settings()['armor_percent'], 120)
        item_balance.cmd_itemscale(self.admin, ['preview', '100'])
        self.assertIn('Level 100', self.admin.send.call_args.args[0])
        item_balance.cmd_itemscale(self.admin, ['reset', 'all'])
        self.assertEqual(item_balance.settings(), item_balance.DEFAULT_SETTINGS)
        player = SimpleNamespace(account=SimpleNamespace(staff_level='player'), send=Mock())
        item_balance.cmd_itemscale(player, ['damage','400'])
        self.assertEqual(item_balance.settings(), item_balance.DEFAULT_SETTINGS)
        self.assertIn('Only administrators',player.send.call_args.args[0])

    def test_armor_protection_live_costs_and_tool_uses(self):
        self.item.update(item_type='armor',wear_loc='body',cost=0)
        self.oset('flags', 'AutoBalance')
        self.assertGreater(item_balance.effective_cost(self.item), 0)
        self.assertEqual(item_types.base_sell_price('A Test Weapon'),
                         max(1,int(item_balance.effective_cost(self.item)*.1)))
        self.player.equipment['body'] = 'A Test Weapon'
        expected = item_balance.effective_armor_bonus(self.item)
        self.assertGreater(expected, 0)
        self.assertEqual(commands.equipped_armor_class_bonus(self.player), expected)
        self.item['stat_bonuses']['armor_class'] = -55
        self.assertEqual(commands.equipped_armor_class_bonus(self.player),55)
        self.item['stat_bonuses'].clear()
        self.item['cost'] = 750
        self.assertEqual(item_balance.effective_cost(self.item),750)
        self.item.update(item_type='tool',wear_loc='tool',max_uses=250)
        self.assertEqual(tool_durability.uses_left('A Test Weapon'),
                         (item_balance.effective_uses(self.item),)*2)
        self.item['max_uses'] = 999
        self.assertEqual(tool_durability.uses_left('A Test Weapon'),(999,999))

    def test_crafted_objects_remain_immune_and_old_items_unchanged(self):
        self.oset('flags','AutoBalance')
        self.item['crafted_vnum_identity'] = True
        self.assertFalse(item_balance.active(self.item))
        self.assertEqual(item_balance.effective_cost(self.item),0)
        self.item.pop('crafted_vnum_identity')
        self.item['level'] = 0
        self.assertFalse(item_balance.active(self.item))
        self.item['level'] = 100
        self.item['extra_flags'] = []
        self.assertFalse(item_balance.active(self.item))

    def test_editor_and_help_are_discoverable(self):
        import help_system
        pages = {page['primary_keyword']:page for page in help_system.DEFAULT_HELP_ENTRIES}
        self.assertIn('itemscale',pages)
        self.assertIn('shop flags',pages)
        self.assertIn('ShopPawnshop', pages['shop flags']['body'])
        self.assertIn('AutoBalance',pages['itemscale']['body'])
        self.assertIn('AutoBalance',olc.VALID_ITEM_EXTRA_FLAGS)
        self.assertIn('ShopMining',olc.VALID_MOB_ACT_FLAGS)
        self.assertIn('itemscale',commands.COMMANDS if hasattr(commands,'COMMANDS') else commands.COMMAND_TABLE)

if __name__ == '__main__':
    unittest.main()
