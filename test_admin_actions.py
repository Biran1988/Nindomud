"""No live data reads/writes: isolate registries and sessions."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock
import admin_actions
import commands
import combat
from session import State


class AdminTests(unittest.TestCase):
    def test_restore_includes_editors_not_closed(self):
        players = [NS(health=1, chakra=2, stamina=3, maximum_health=123,
                      maximum_chakra=234, maximum_stamina=345) for _ in range(3)]
        sessions = [NS(player=p, state=s, send=Mock(), send_prompt=Mock())
                    for p, s in zip(players, [State.PLAYING, State.EDITING, State.CLOSED])]
        with patch('session.ACTIVE_SESSIONS', sessions):
            self.assertEqual(admin_actions.restore_online(), 2)
        for p in players[:2]:
            self.assertEqual((p.health, p.chakra, p.stamina), (123, 234, 345))
        self.assertEqual(players[2].health, 1)
        sessions[1].send_prompt.assert_not_called()

    def test_permissions_and_argument_validation(self):
        with patch('admin_actions.restore_online') as restore, patch('admin_actions.respawn_missing') as respawn:
            for role in ('player', 'helper', 'builder', 'area leader'):
                s = NS(account=NS(staff_level=role), send=Mock())
                commands.cmd_restore(s, [])
                commands.cmd_respawn(s, [])
            restore.assert_not_called()
            respawn.assert_not_called()
            for role in ('administrator', 'implementor'):
                s = NS(account=NS(staff_level=role), send=Mock())
                commands.cmd_restore(s, [])
                commands.cmd_respawn(s, [])
            self.assertEqual(restore.call_count, 2)
            self.assertEqual(respawn.call_count, 2)
            commands.cmd_restore(s, ['someone'])
            commands.cmd_respawn(s, ['extra'])
            self.assertEqual(restore.call_count, 2)
            self.assertEqual(respawn.call_count, 2)

    def test_respawn_caps_wanderers_queue_and_repeat(self):
        points = [dict(kind='mob', vnum=1, room_vnum=10, total_cap=3, per_period_cap=1),
                  dict(kind='mob', vnum=2, room_vnum=11),
                  dict(kind='mob', vnum=4, room_vnum=500),
                  dict(kind='mob', vnum=5, room_vnum=12),
                  dict(kind='mob', vnum=6, room_vnum=999),
                  dict(kind='item', vnum=7, room_vnum=10)]
        living = {20: [NS(template_vnum=1, health=7), NS(template_vnum=2, health=8)]}
        queue = [(9999999999, 1, 10), (9999999999, 3, 15)]
        templates = {n: dict(combat.DEFAULT_MOB_FIELDS, level=1, hit_dice='1d6', damage_dice='1d2')
                     for n in range(1, 8)}
        templates[5]['enabled'] = False
        with patch('areas.all_areas', return_value={'a': dict(vnum_start=1, vnum_end=99)}), \
             patch('spawn_points.list_spawn_points', return_value=points), \
             patch('world.WORLD.get', side_effect=lambda n: None if n == 999 else object()), \
             patch.object(combat, 'MOBS_BY_ROOM', living), \
             patch.object(combat, 'MOB_TEMPLATES', templates), \
             patch.object(combat, '_respawn_queue', queue):
            self.assertEqual(admin_actions.respawn_missing(), 4)
            self.assertEqual(admin_actions.respawn_missing(), 0)
            self.assertEqual(queue, [])
            self.assertEqual(living[20][0].health, 7)
            self.assertEqual(sum(m.template_vnum == 1 for ms in living.values() for m in ms), 3)
            self.assertEqual(sum(m.template_vnum == 2 for ms in living.values() for m in ms), 1)
            self.assertFalse(any(m.template_vnum in (5, 6, 7) for ms in living.values() for m in ms))


if __name__ == '__main__':
    unittest.main()
