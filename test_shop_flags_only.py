"""Regression contract: NPC merchants are configured ONLY by mob flags."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import combat
import commands
import data_shops
import olc
import shop_flags
import spawn_points
import world_persistence


class FlagOnlyShopTests(unittest.TestCase):
    def setUp(self):
        self.vnum = 999123
        self.mob = combat.default_template(self.vnum, 'a merchant')
        self.templates = patch.object(combat, 'MOB_TEMPLATES', {self.vnum: self.mob})
        self.templates.start()
        self.addCleanup(self.templates.stop)
        self.admin = SimpleNamespace(
            player=SimpleNamespace(name='Builder', room_vnum=1),
            account=SimpleNamespace(staff_level='implementor'), send=Mock())
        self.logs = patch.object(olc, '_log')
        self.logs.start()
        self.addCleanup(self.logs.stop)

    def edit(self, *args):
        olc.cmd_mset(self.admin, [str(self.vnum), *args])

    def test_shop_type_and_bool_are_not_editor_fields(self):
        reference = olc._mset_field_reference(False)
        self.assertNotIn('shoptype', reference.lower())
        self.assertNotIn('shopkeeper', reference.lower().split('&won / off&x', 1)[1].split('&wlists', 1)[0])
        for args in [('shoptype', 'pawnshop'), ('shoptype',),
                     ('shopkeeper', 'on'), ('shopkeeper', 'off')]:
            with self.subTest(args=args):
                self.edit(*args)
                self.assertIn('FLAGS', self.admin.send.call_args.args[0])
                self.assertFalse(combat.is_shopkeeper(SimpleNamespace(template_vnum=self.vnum)))
        self.edit('flags', 'ShopPawnshop')
        self.assertTrue(combat.is_shopkeeper(SimpleNamespace(template_vnum=self.vnum)))
        self.assertEqual(shop_flags.shop_type(self.mob), 'pawnshop')
        self.assertNotIn('shop_type', self.mob)
        self.assertNotIn('shopkeeper', self.mob)

    def test_stale_legacy_fields_cannot_override_flags(self):
        self.edit('flags', 'ShopMining')
        self.mob.update(shop_type='pawnshop', shopkeeper=False,
                        shop_buys_categories=['food'])
        self.assertEqual(shop_flags.shop_type(self.mob), 'mining')
        instance=SimpleNamespace(template_vnum=self.vnum)
        self.assertTrue(combat.is_shopkeeper(instance))
        self.assertEqual(combat.mob_shop_buys_categories(instance), ['ore'])
        self.assertTrue(commands._npc_shop_accepts(instance, 'An Iron Ore', 'ore'))
        self.assertFalse(commands._npc_shop_accepts(instance, 'A Carrot', 'food'))
        self.edit('flags', '-Shopkeeper')
        self.assertFalse(combat.is_shopkeeper(instance))
        self.assertFalse(shop_flags.has_shop_flag(self.mob))
        self.assertNotIn('shop_type', self.mob)
        self.assertNotIn('shopkeeper', self.mob)

    def test_old_world_snapshot_upgrades_shopkeeper_without_losing_stock(self):
        legacy = combat.default_template(self.vnum, 'a legacy pawnbroker')
        legacy.update(shopkeeper=True, shop_type='pawnshop',
                      shop_items=[99901, 99902])
        state={'rooms':{},'mobs':{str(self.vnum):legacy},'items':{}}
        with patch('storage.load_world_state', return_value=state), \
             patch('storage.load_custom_templates', return_value={'mobs':{},'items':{}}), \
             patch('door_links.reconcile_all'):
            world_persistence.apply_saved_world()
        template=combat.MOB_TEMPLATES[self.vnum]
        self.assertEqual(shop_flags.shop_type(template), 'pawnshop')
        self.assertTrue(shop_flags.is_shopkeeper_template(template))
        self.assertEqual(template['shop_items'], [99901, 99902])
        self.assertNotIn('shop_type',template)
        self.assertNotIn('shopkeeper',template)
        shop_flags.disable_shopkeeper(template)
        self.assertFalse(shop_flags.is_shopkeeper_template(template))

    def test_old_spawn_template_upgrades_without_overriding_flagged_specialty(self):
        legacy = combat.default_template(self.vnum, 'a legacy buyer')
        legacy.update(shopkeeper=True, shop_type='farming', shop_items=[321])
        with patch('storage.load_custom_templates', return_value={
             'mobs':{str(self.vnum):legacy}, 'items':{}}):
            spawn_points.restore_custom_templates()
        self.assertEqual(shop_flags.shop_type(combat.MOB_TEMPLATES[self.vnum]), 'farming')
        self.assertEqual(combat.MOB_TEMPLATES[self.vnum]['shop_items'], [321])
        shop_flags.set_type(combat.MOB_TEMPLATES[self.vnum], 'gemcutter')
        self.assertEqual(shop_flags.shop_type(combat.MOB_TEMPLATES[self.vnum]), 'gemcutter')

    def test_simple_shopkeeper_preserves_manual_category_flexibility(self):
        shop_flags.enable_shopkeeper(self.mob)
        self.mob['shop_buys_categories']=['weapon', 'armor']
        instance=SimpleNamespace(template_vnum=self.vnum)
        self.assertEqual(combat.mob_shop_buys_categories(instance), ['weapon','armor'])
        self.assertEqual(commands._npc_shop_sale_multiplier(instance), 1.0)
        shop_flags.set_type(self.mob, 'ShopMining'.removeprefix('Shop').lower())
        self.assertEqual(combat.mob_shop_buys_categories(instance), ['ore'])
        self.assertEqual(commands._npc_shop_sale_multiplier(instance), 1.5)


if __name__ == '__main__':
    unittest.main()
