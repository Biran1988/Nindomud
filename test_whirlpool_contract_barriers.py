"""New Whirlpool barrier, travel-anchoring and opt-in contract tests."""
import time
import unittest
from unittest.mock import patch

import commands
import data_jutsu
import jutsu_balance
import sage_mode
import storage
import whirlpool_fuinjutsu as seals
import world
from test_whirlpool_fuinjutsu import WhirlpoolFuinjutsuTests


class WhirlpoolExpansionTests(unittest.TestCase):
    setUp = WhirlpoolFuinjutsuTests.setUp
    player = WhirlpoolFuinjutsuTests.player
    run_jutsu = WhirlpoolFuinjutsuTests.run_jutsu

    def test_multi_wall_is_atomic_and_persists_offline(self):
        caster = self.caster
        original = caster.player.chakra
        self.run_jutsu(caster, 'multi exit barrier')
        self.assertEqual(caster.player.chakra, original - jutsu_balance.cast_cost(caster.player, data_jutsu.JUTSU["multi exit barrier"], "chakra"))
        self.assertEqual({r['direction'] for r in seals._load()}, {'north', 'east'})
        self.assertTrue(all(235 < r['expires_at'] - time.time() <= 241 for r in seals._load()))
        caster.player.room_vnum = 2
        import session
        session.ACTIVE_SESSIONS.remove(caster)
        self.assertTrue(seals.current_barrier(1, 'east'))
        self.assertTrue(seals.current_barrier(1, 'north'))

    def test_multi_wall_skips_protected_destinations_and_needs_no_args(self):
        before = self.caster.player.chakra
        self.run_jutsu(self.caster, 'multi exit barrier')
        self.assertEqual({r['direction'] for r in seals._load()}, {'north', 'east'})
        self.assertIsNone(seals.current_barrier(1, 'south'))  # safe destination
        paid = jutsu_balance.cast_cost(
            self.caster.player, data_jutsu.JUTSU["multi exit barrier"], "chakra")
        self.assertEqual(self.caster.player.chakra, before - paid)
        self.run_jutsu(self.caster, 'multi exit barrier north east')
        self.assertEqual(len(seals._load()), 2)  # explicit arguments are rejected
        self.assertEqual(self.caster.player.chakra, before - paid)

    def test_multi_wall_detects_more_than_three_exits_including_vertical(self):
        for direction in ('west', 'northeast', 'up', 'inside'):
            world.WORLD.link(1, direction, 2, bidirectional=False)
        self.run_jutsu(self.caster, 'multi exit barrier')
        records = seals._load()
        self.assertEqual({r['direction'] for r in records},
                         {'north', 'east', 'west', 'northeast', 'up', 'inside'})
        self.assertEqual(len({r['array_id'] for r in records}), 1)
        self.assertEqual(seals._caster_barrier_count(records, 'Caster'), 1)
        self.assertTrue(all(seals.current_barrier(1, d) for d in
                            ('north', 'east', 'west', 'northeast', 'up', 'inside')))
        self.assertIsNone(seals.current_barrier(1, 'south'))

    def test_multi_wall_skips_already_sealed_exit(self):
        self.run_jutsu(self.caster, 'timed barrier seal north')
        original = seals.current_barrier(1, 'north')
        self.run_jutsu(self.caster, 'multi exit barrier')
        records = seals._load()
        self.assertEqual(len(records), 2)
        self.assertEqual(seals.current_barrier(1, 'north'), original)
        self.assertIsNotNone(seals.current_barrier(1, 'east'))
        self.assertEqual(seals._caster_barrier_count(records, 'Caster'), 2)
        chakra = self.caster.player.chakra
        self.caster.player.cooldowns['multi exit barrier'] = 0
        self.run_jutsu(self.caster, 'multi exit barrier')  # no eligible exits left
        self.assertEqual(self.caster.player.chakra, chakra)
        self.assertEqual(len(seals._load()), 2)

    def test_multi_wall_no_eligible_exits_does_not_charge(self):
        world.WORLD.add_room(world.Room(5, 'Dead end', 'Protected passage.'))
        world.WORLD.link(5, 'north', 4, bidirectional=False)  # safe destination
        self.caster.player.room_vnum = 5
        before = self.caster.player.chakra
        self.run_jutsu(self.caster, 'multi exit barrier')
        self.assertEqual(seals._load(), [])
        self.assertEqual(self.caster.player.chakra, before)

    def test_multi_wall_counts_one_cast_toward_three_cast_limit(self):
        for direction in ('west', 'up'):
            world.WORLD.link(1, direction, 2, bidirectional=False)
        self.run_jutsu(self.caster, 'multi exit barrier')
        self.caster.player.room_vnum = 2
        self.run_jutsu(self.caster, 'timed barrier seal south')
        world.WORLD.link(2, 'east', 3, bidirectional=False)
        self.caster.player.cooldowns['timed barrier seal'] = 0
        self.run_jutsu(self.caster, 'timed barrier seal east')
        self.assertEqual(seals._caster_barrier_count(seals._load(), 'Caster'), 3)
        world.WORLD.link(2, 'west', 3, bidirectional=False)
        self.caster.player.cooldowns['timed barrier seal'] = 0
        before = self.caster.player.chakra
        self.run_jutsu(self.caster, 'timed barrier seal west')
        self.assertEqual(self.caster.player.chakra, before)
        self.assertIsNone(seals.current_barrier(2, 'west'))

    def test_anchor_blocks_anki_and_recall_but_walking_works(self):
        self.run_jutsu(self.caster, 'teleportation anchor seal Opponent')
        self.assertTrue(seals.blocks_teleport(self.enemy.player))
        self.enemy.player.apartment_room_vnum = 2
        before = self.enemy.player.room_vnum
        commands.cmd_recall(self.enemy, [])
        commands.cmd_anki(self.enemy, [])
        self.assertEqual(self.enemy.player.room_vnum, before)
        commands.cmd_move(self.enemy, 'east')
        self.assertEqual(self.enemy.player.room_vnum, 3)
        self.enemy.player.active_status_effects['fuinjutsu_teleport_anchor']['expires_at'] = time.time() - 1
        self.assertFalse(seals.blocks_teleport(self.enemy.player))

    def test_contract_seal_blocks_summon_without_removing_contract(self):
        self.enemy.player.signed_summoning_contracts = ['toad']
        self.enemy.player.level = 95
        self.run_jutsu(self.caster, 'summoning contract seal Opponent')
        self.assertTrue(seals.blocks_summoning(self.enemy.player))
        initial_chakra = self.enemy.player.chakra
        sage_mode.summon_command(self.enemy, ['toad'])
        self.assertEqual(self.enemy.player.chakra, initial_chakra)
        self.assertEqual(self.enemy.player.signed_summoning_contracts, ['toad'])
        self.enemy.player.active_status_effects['fuinjutsu_summon_locked']['expires_at'] = time.time() - 1
        self.assertFalse(seals.blocks_summoning(self.enemy.player))

    def _contract_pair(self):
        a, a_out = self.player('Alpha', village='leaf', clan='nara', level=95)
        b, b_out = self.player('Beta', village='leaf', clan='nara', level=95)
        a.player.signed_summoning_contracts = ['toad']
        a.player.sage_active_contract = 'toad'
        a.player.sage_preferred_contract = 'toad'
        a.player.sage_mastery = {'toad': 100}
        a.player.sage_training_ready_at = {'toad': 123}
        b.player.signed_summoning_contracts = ['snake']
        b.player.sage_mastery = {'snake': 33}
        self.caster.player.level = 230
        seals.sync_skills(self.caster.player)
        self.caster.player.signed_summoning_contracts = ['slug']
        self.addCleanup(seals._PENDING_BREAKS.clear)
        return a, a_out, b, b_out

    def test_break_two_consents_does_not_affect_caster(self):
        a, ao, b, bo = self._contract_pair()
        old_chakra = self.caster.player.chakra
        self.run_jutsu(self.caster, 'summoning contract break Alpha Beta')
        self.assertEqual(self.caster.player.chakra, old_chakra)
        self.assertIn("Type 'yes'", '\n'.join(ao))
        self.assertIn("Type 'yes'", '\n'.join(bo))
        commands.dispatch_line(a, 'yes')
        self.assertEqual(a.player.signed_summoning_contracts, ['toad'])
        self.assertEqual(b.player.signed_summoning_contracts, ['snake'])
        commands.dispatch_line(b, 'yes')
        self.assertEqual(self.caster.player.chakra, old_chakra - jutsu_balance.cast_cost(self.caster.player, data_jutsu.JUTSU["summoning contract break"], "chakra"))
        self.assertEqual(self.caster.player.signed_summoning_contracts, ['slug'])
        self.assertEqual(a.player.signed_summoning_contracts, [])
        self.assertEqual(b.player.signed_summoning_contracts, [])
        self.assertEqual(a.player.sage_active_contract, '')
        self.assertEqual(a.player.sage_mastery, {})
        self.assertEqual(b.player.sage_mastery, {})
        self.assertEqual(storage.load_player('Alpha').signed_summoning_contracts, [])
        self.assertEqual(storage.load_player('Beta').signed_summoning_contracts, [])

    def test_break_dismisses_active_summons_and_sage_mode(self):
        import combat
        import data_summons
        a, _, b, _ = self._contract_pair()
        combat.spawn_summon(a.player, data_summons.best_available_tier('toad', a.player.level))
        combat.spawn_summon(b.player, data_summons.best_available_tier('snake', b.player.level))
        self.assertIsNotNone(combat.active_summon(a.player))
        self.assertIsNotNone(combat.active_summon(b.player))
        self.run_jutsu(self.caster, 'summoning contract break Alpha Beta')
        commands.dispatch_line(a, 'yes')
        commands.dispatch_line(b, 'yes')
        self.assertIsNone(combat.active_summon(a.player))
        self.assertIsNone(combat.active_summon(b.player))
        self.assertEqual(a.player.sage_active_contract, '')

    def test_anchor_prevents_kamui_and_tsukuyomi_transfers(self):
        import mangekyo
        self.run_jutsu(self.caster, 'teleportation anchor seal Opponent')
        original_room = self.enemy.player.room_vnum
        with self.assertRaisesRegex(ValueError, 'teleportation anchor'):
            mangekyo.open_pocket_dimension(self.caster, self.enemy, world)
        with self.assertRaisesRegex(ValueError, 'teleportation anchor'):
            mangekyo.open_tsukuyomi(self.caster, self.enemy, world)
        self.assertEqual(self.enemy.player.room_vnum, original_room)
        self.assertIsNone(self.caster.player.kamui_pocket_dimension_vnum)

    def test_break_refusal_never_charges_or_changes_contract(self):
        a, _, b, _ = self._contract_pair()
        before = self.caster.player.chakra
        self.run_jutsu(self.caster, 'summoning contract break Alpha Beta')
        commands.dispatch_line(a, 'yes')
        commands.dispatch_line(b, 'no')
        self.assertFalse(seals._PENDING_BREAKS)
        self.assertEqual(a.player.signed_summoning_contracts, ['toad'])
        self.assertEqual(b.player.signed_summoning_contracts, ['snake'])
        self.assertEqual(self.caster.player.chakra, before)

    def test_break_requires_two_unique_noncasters_with_contracts_and_expires(self):
        a, _, b, _ = self._contract_pair()
        self.run_jutsu(self.caster, 'summoning contract break Caster Beta')
        self.assertFalse(seals._PENDING_BREAKS)
        self.run_jutsu(self.caster, 'summoning contract break Alpha Alpha')
        self.assertFalse(seals._PENDING_BREAKS)
        self.run_jutsu(self.caster, 'summoning contract break Alpha Beta')
        self.assertEqual(len(seals._PENDING_BREAKS), 1)
        req = seals._PENDING_BREAKS[self.caster]
        seals._purge_expired_breaks(now=req['expires'] + 1)
        self.assertFalse(seals._PENDING_BREAKS)
        commands.dispatch_line(a, 'yes')
        self.assertEqual(a.player.signed_summoning_contracts, ['toad'])
        self.assertEqual(b.player.signed_summoning_contracts, ['snake'])

    def test_break_drops_on_teleport_or_logout_before_other_consent(self):
        a, _, b, _ = self._contract_pair()
        self.run_jutsu(self.caster, 'summoning contract break Alpha Beta')
        commands.dispatch_line(a, 'yes')
        b.player.room_vnum = 2
        commands.dispatch_line(b, 'yes')
        self.assertFalse(seals._PENDING_BREAKS)
        self.assertEqual(a.player.signed_summoning_contracts, ['toad'])
        self.assertEqual(b.player.signed_summoning_contracts, ['snake'])

if __name__ == '__main__':
    unittest.main()
