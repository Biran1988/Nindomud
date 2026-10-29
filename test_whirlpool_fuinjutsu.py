"""Behavioral coverage of clan restrictions, status locks, remote walls and save journal."""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import commands
import combat
import data_jutsu
import leveling
import regen
import session as sessions
import status_effects
import storage
import whirlpool_fuinjutsu as seals
import world
from models import Account, Player
from session import Session, State


class WhirlpoolFuinjutsuTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for patcher in (
            patch.object(storage, 'DATA_DIR', tmp.name),
            patch.object(storage, 'PLAYERS_DIR', os.path.join(tmp.name, 'players')),
            patch.object(storage, 'ACCOUNTS_DIR', os.path.join(tmp.name, 'accounts')),
            patch.object(world.WORLD, 'rooms', {}),
            patch.object(sessions, 'ACTIVE_SESSIONS', []),
            patch.object(combat, 'MOBS_BY_ROOM', {}),
            patch.object(commands.olc, '_require_assigned_vnum', return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        for vnum, safe in ((1, False), (2, False), (3, False), (4, True)):
            world.WORLD.add_room(world.Room(vnum, f'Testing room {vnum}', 'Test clearing.', safe=safe))
        world.WORLD.link(1, 'north', 2)
        world.WORLD.link(1, 'east', 3)
        world.WORLD.link(1, 'south', 4)
        self.caster, self.caster_out = self.player('Caster')
        self.enemy, self.enemy_out = self.player('Opponent', village='leaf', clan='nara')

    def player(self, name, village='whirlpool', clan='uzumaki', level=250):
        out = []
        s = Session(out.append, lambda: None)
        s.account = Account(name=name, salt_hex='x', hash_hex='y')
        s.player = Player(name=name, account_name=name, village=village, clan=clan,
                          level=level, primary_class='ninjutsu', room_vnum=1,
                          chakra=3000, maximum_chakra=3000,
                          stamina=300, maximum_stamina=300,
                          health=300, maximum_health=300)
        s.state = State.PLAYING
        if s not in sessions.ACTIVE_SESSIONS:
            sessions.ACTIVE_SESSIONS.append(s)
        seals.sync_skills(s.player)
        out.clear()
        return s, out

    def run_jutsu(self, s, words):
        commands.dispatch_line(s, f'perform {words}')

    def test_roster_not_granted_to_non_whirlpool(self):
        self.assertEqual(len(seals.jutsu_entries()), 14)
        player = self.enemy.player
        learned = set(player.learned_skills)
        leveling.sync_universal_skills(player)
        self.assertFalse(set(x['display_name'] for x in seals.jutsu_entries().values()) & set(player.learned_skills))
        self.assertFalse('Chakra Suppression Seal' in '\n'.join(commands.build_jutsu_catalog_lines(player)))
        self.run_jutsu(self.enemy, 'chakra suppression seal Caster')
        self.assertTrue(any('only ninja' in s.lower() for s in self.enemy_out), self.enemy_out)
        self.assertEqual(self.enemy.player.chakra, 3000)

    def test_reject_other_uzumaki_village_and_level(self):
        self.caster.player.village = 'leaf'
        self.run_jutsu(self.caster, 'chakra suppression seal Opponent')
        self.assertTrue(any('only ninja' in s.lower() for s in self.caster_out))
        self.caster.player.village = 'whirlpool'
        self.caster.player.level = 20
        self.run_jutsu(self.caster, 'chakra suppression seal Opponent')
        self.assertTrue(any('not learned' in s.lower() for s in self.caster_out))

    def test_level_sync_only_grants_rank_eligible_and_not_generic(self):
        novice, _ = self.player('Novice', level=25)
        names = {v['display_name'] for v in seals.jutsu_entries().values()}
        self.assertIn('Chakra Suppression Seal', novice.player.learned_skills)
        self.assertNotIn('Mind Suppression Seal', novice.player.learned_skills)
        self.assertNotIn('Imbued Barrier Seal', novice.player.learned_skills)
        self.assertEqual(len(names & set(novice.player.learned_skills)), 1)
        novice.player.level = 135
        changes = seals.sync_skills(novice.player)
        self.assertIn('Imbued Barrier Seal', changes)
        self.assertEqual(len(names & set(novice.player.learned_skills)), 10)
        novice.player.level = 230
        seals.sync_skills(novice.player)
        self.assertEqual(len(names & set(novice.player.learned_skills)), 14)

    def test_ninjutsu_and_genjutsu_sealed_independently(self):
        target = self.enemy.player
        target.learned_skills.extend(['Shadow Shuriken Technique', 'Demonic Illusion: Hell Viewing Technique'])
        self.run_jutsu(self.caster, 'chakra suppression seal Opponent')
        self.assertIn('fuinjutsu_no_ninjutsu', target.active_status_effects)
        self.assertIsNotNone(seals.blocked_jutsu(target, data_jutsu.JUTSU['shadow shuriken technique']))
        self.assertIsNone(seals.blocked_jutsu(target, data_jutsu.JUTSU['demonic illusion hell viewing technique']))
        self.assertFalse(combat._can_use_jutsu(target, data_jutsu.JUTSU['shadow shuriken technique']))
        self.assertTrue(combat._can_use_jutsu(target, data_jutsu.JUTSU['demonic illusion hell viewing technique']))
        # Use a different cooldown/technique for the other lock.
        self.run_jutsu(self.caster, 'mind suppression seal Opponent')
        self.assertIn('fuinjutsu_no_genjutsu', target.active_status_effects)
        self.assertFalse(combat._can_use_jutsu(target, data_jutsu.JUTSU['demonic illusion hell viewing technique']))
        self.assertEqual(target.health, 300)
        self.assertEqual(storage.load_player('Opponent').active_status_effects['fuinjutsu_no_genjutsu']['duration'], 18)

    def test_hand_sign_lock_blocks_both_and_whirlpool_fuinjutsu(self):
        self.run_jutsu(self.caster, 'hand sign suppression seal Opponent')
        t = self.enemy.player
        for key in ('shadow shuriken technique', 'demonic illusion hell viewing technique', 'chakra suppression seal'):
            self.assertIsNotNone(seals.blocked_jutsu(t, data_jutsu.JUTSU[key]))
        t.active_status_effects['fuinjutsu_no_handsigns']['expires_at'] = time.time() - 1
        self.assertIsNone(seals.blocked_jutsu(t, data_jutsu.JUTSU['shadow shuriken technique']))

    def test_chakra_lock_stops_charge_and_regen_but_not_health(self):
        target = self.enemy.player
        target.chakra = 50
        self.enemy.chakra_charge = {'total': 20}
        self.run_jutsu(self.caster, 'chakra lock seal Opponent')
        self.assertIsNone(self.enemy.chakra_charge)
        commands.cmd_charge(self.enemy, [])
        self.assertIn('sealed', '\n'.join(self.enemy_out).lower())
        before = target.chakra
        regen.tick_player(target)
        self.assertEqual(target.chakra, before)
        target.active_status_effects['fuinjutsu_chakra_locked']['expires_at'] = time.time() - 1
        regen.tick_player(target)
        self.assertGreater(target.chakra, before)

    def test_root_stops_movement_without_spending_stamina(self):
        self.run_jutsu(self.caster, 'binding formula seal Opponent')
        before = self.enemy.player.stamina
        commands.cmd_move(self.enemy, 'north')
        self.assertEqual(self.enemy.player.room_vnum, 1)
        self.assertEqual(self.enemy.player.stamina, before)
        self.enemy.player.active_status_effects['fuinjutsu_rooted']['expires_at'] = time.time() - 1
        commands.cmd_move(self.enemy, 'north')
        self.assertEqual(self.enemy.player.room_vnum, 2)

    def test_chakra_siphon_drains_and_restores(self):
        self.caster.player.chakra = 2000
        self.enemy.player.chakra = 700
        self.run_jutsu(self.caster, 'chakra siphon seal Opponent')
        self.assertEqual(self.enemy.player.chakra, 100)
        self.assertEqual(self.caster.player.chakra, 2000 - 50 + 300)
        self.run_jutsu(self.caster, 'chakra siphon seal Opponent')
        self.assertEqual(self.enemy.player.chakra, 100)

    def test_safe_rooms_prevent_hostile_seals_and_walls(self):
        self.enemy.player.room_vnum = self.caster.player.room_vnum = 4
        before = self.caster.player.chakra
        self.run_jutsu(self.caster, 'chakra suppression seal Opponent')
        self.assertEqual(self.caster.player.chakra, before)
        self.caster.player.room_vnum = 1
        self.run_jutsu(self.caster, 'timed barrier seal south')
        self.assertEqual(self.caster.player.chakra, before)
        self.assertIsNone(seals.current_barrier(1, 'south'))

    def test_timed_wall_blocks_only_direction_not_reverse_and_survives_caster_leaving(self):
        self.run_jutsu(self.caster, 'timed barrier seal north')
        self.assertIsNotNone(seals.current_barrier(1, 'north'))
        self.assertIn('(sealed)', ' '.join(commands._format_exits(world.WORLD.get(1))))
        old = self.enemy.player.stamina
        commands.cmd_move(self.enemy, 'north')
        self.assertEqual(self.enemy.player.room_vnum, 1)
        self.assertEqual(self.enemy.player.stamina, old)
        self.caster.player.room_vnum = 3
        self.enemy.player.room_vnum = 2
        commands.cmd_move(self.enemy, 'south')
        self.assertEqual(self.enemy.player.room_vnum, 1)
        self.assertIsNotNone(seals.current_barrier(1, 'north'))
        with open(seals._path()) as f:
            saved = json.load(f)
        self.assertEqual(saved[0]['direction'], 'north')
        self.assertEqual(saved[0]['mode'], 'timed')
        self.assertEqual(saved[0]['caster'], 'Caster')

    def test_timed_wall_outlives_offline_caster_until_expiry(self):
        self.run_jutsu(self.caster, 'timed barrier seal north')
        record = seals.current_barrier(1, 'north')
        sessions.ACTIVE_SESSIONS.remove(self.caster)
        self.assertIsNotNone(seals.current_barrier(1, 'north'))
        self.assertIsNone(seals.current_barrier(1, 'north', now=record['expires_at'] + .1))
        seals.process_barriers(now=record['expires_at'] + .1)
        self.assertEqual(seals._load(), [])

    def test_imbued_wall_charges_exact_amount_and_duration_scales(self):
        self.run_jutsu(self.caster, 'imbued barrier seal east 200')
        record = seals.current_barrier(1, 'east')
        self.assertEqual(self.caster.player.chakra, 2800)
        self.assertEqual(record['mode'], 'imbued')
        self.assertEqual(record['imbued_chakra'], 200)
        self.assertAlmostEqual(record['expires_at'] - time.time(), 600, delta=3)
        sessions.ACTIVE_SESSIONS.remove(self.caster)
        self.assertIsNotNone(seals.current_barrier(1, 'east'))

    def test_imbue_input_validation_and_no_duplicate_stacking(self):
        before = self.caster.player.chakra
        for args in ('east', 'east 49', 'east 1001', 'west 200', 'south 200'):
            self.run_jutsu(self.caster, 'imbued barrier seal ' + args)
        self.assertEqual(self.caster.player.chakra, before)
        self.run_jutsu(self.caster, 'imbued barrier seal east 100')
        self.assertEqual(self.caster.player.chakra, 2900)
        self.run_jutsu(self.caster, 'timed barrier seal east')
        self.assertEqual(len(seals._load()), 1)
        self.assertEqual(self.caster.player.chakra, 2900)

    def test_flowing_wall_upkeep_and_chakra_failure_even_in_other_room(self):
        self.run_jutsu(self.caster, 'flowing barrier seal north')
        self.caster.player.room_vnum = 3
        record = seals.current_barrier(1, 'north')
        before = self.caster.player.chakra
        seals.process_barriers(now=record['next_upkeep_at'] + .01)
        self.assertEqual(self.caster.player.chakra, before - seals.UPKEEP_COST)
        self.assertIsNotNone(seals.current_barrier(1, 'north'))
        self.caster.player.chakra = 0
        record = seals.current_barrier(1, 'north')
        seals.process_barriers(now=record['next_upkeep_at'] + .01)
        self.assertIsNone(seals.current_barrier(1, 'north'))

    def test_flowing_wall_breaks_offline_without_affecting_other_walls(self):
        self.run_jutsu(self.caster, 'flowing barrier seal north')
        self.run_jutsu(self.caster, 'timed barrier seal east')
        self.caster.state = State.LINKDEAD
        seals.process_barriers()
        self.assertIsNone(seals.current_barrier(1, 'north'))
        self.assertIsNotNone(seals.current_barrier(1, 'east'))

    def test_release_remote_and_target_seals_but_not_reaper(self):
        self.run_jutsu(self.caster, 'timed barrier seal north')
        self.caster.player.room_vnum = 3
        self.run_jutsu(self.caster, 'seal release barriers')
        self.assertIsNone(seals.current_barrier(1, 'north'))
        self.caster.player.room_vnum = 1
        self.run_jutsu(self.caster, 'chakra suppression seal Opponent')
        self.assertIn('fuinjutsu_no_ninjutsu', self.enemy.player.active_status_effects)
        self.caster.player.cooldowns['seal release'] = 0  # test separate release usage
        self.run_jutsu(self.caster, 'seal release Opponent')
        self.assertNotIn('fuinjutsu_no_ninjutsu', self.enemy.player.active_status_effects)
        self.assertEqual(self.enemy.player.reaper_seal_id, '')

    def test_wall_removed_when_builder_changes_exit(self):
        self.run_jutsu(self.caster, 'timed barrier seal north')
        world.WORLD.get(1).exits['north'] = 3
        self.assertIsNone(seals.current_barrier(1, 'north'))
        seals.process_barriers()
        self.assertEqual(seals._load(), [])

    def test_cannot_exceed_three_active_walls(self):
        world.WORLD.link(2, 'east', 3, bidirectional=False)
        for direction in ('north', 'east'):
            self.run_jutsu(self.caster, 'timed barrier seal ' + direction)
            self.caster.player.cooldowns['timed barrier seal'] = 0
        self.caster.player.room_vnum = 2
        self.run_jutsu(self.caster, 'flowing barrier seal east')
        self.caster.player.room_vnum = 1
        self.run_jutsu(self.caster, 'imbued barrier seal north 100')
        self.assertEqual(len(seals._load()), 3)
        self.assertEqual(self.caster.player.chakra, 3000 - 75 * 2 - 36)


if __name__ == '__main__':
    unittest.main()
