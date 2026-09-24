import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import combat
import olc
import data_classes
import colors


class MobClassTests(unittest.TestCase):
    def setUp(self):
        self.template = combat.default_template(90001, 'test ninja')
        for target, value in [('combat.MOB_TEMPLATES', {90001: self.template}),
                              ('combat.MOBS_BY_ROOM', {})]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch('olc._log')
        p.start()
        self.addCleanup(p.stop)
        self.session = NS(account=NS(staff_level='implementor'),
                          player=NS(name='Builder'), send=Mock())

    def test_default_and_legacy(self):
        self.assertNotIn('race', self.template)
        self.assertNotIn('char_class', self.template)
        self.assertIsNone(combat.spawn_mob(90001, 1).primary_class)
        self.template.update(race='Human', char_class='Warrior', primary_class='Mage')
        self.assertIsNone(combat.spawn_mob(90001, 1).primary_class)

    def test_set_clear_and_live_updates(self):
        mob = combat.spawn_mob(90001, 1)
        for name in data_classes.CLASSES:
            olc.cmd_mset(self.session, ['90001', 'class', name])
            self.assertEqual(self.template['primary_class'], name)
            self.assertEqual(mob.primary_class, name)
            self.assertEqual(combat.spawn_mob(90001, 1).primary_class, name)
        olc.cmd_mset(self.session, ['90001', 'class', 'none'])
        self.assertIsNone(self.template['primary_class'])
        self.assertTrue(all(m.primary_class is None for m in combat.MOBS_BY_ROOM[1]))

    def test_reject_old_fields_and_classes(self):
        for field, value in [('race', 'Human'), ('char_class', 'Warrior'), ('class', 'Warrior')]:
            olc.cmd_mset(self.session, ['90001', field, value])
        self.assertNotIn('race', self.template)
        self.assertNotIn('char_class', self.template)
        self.assertIsNone(self.template['primary_class'])

    def test_mstat_has_no_race_or_legacy_class(self):
        self.template.update(race='Human', char_class='Warrior')
        olc.cmd_mstat(self.session, ['90001'])
        output = ''.join(c.args[0] for c in self.session.send.call_args_list)
        self.assertNotIn('Race:', output)
        self.assertNotIn('Warrior', output)
        self.assertIn('None', output)

    def test_mset_fields_are_wrapped_and_player_fields_are_separate(self):
        olc.cmd_mset(self.session, ['fields'])
        mob_reference = colors.render(self.session.send.call_args.args[0], False)
        self.assertIn('MOB FIELDS', mob_reference)
        self.assertIn('short', mob_reference)
        self.assertIn('flags', mob_reference)
        self.assertIn('shopbuyscategories', mob_reference)
        self.assertNotIn('maximum_health', mob_reference)
        self.assertTrue(all(len(line) <= 80 for line in mob_reference.splitlines()))

        olc.cmd_mset(self.session, ['fields', 'player'])
        player_reference = colors.render(self.session.send.call_args.args[0], False)
        self.assertIn('PLAYER FIELDS', player_reference)
        self.assertIn('maximumhealth', player_reference)
        self.assertIn('rank', player_reference)
        self.assertNotIn('shopbuyscategories', player_reference)
        self.assertTrue(all(len(line) <= 80 for line in player_reference.splitlines()))


if __name__ == '__main__':
    unittest.main()
