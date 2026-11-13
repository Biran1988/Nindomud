"""Trade consent and conservation checks through real commands and transfers."""
import unittest
from types import SimpleNamespace as NS

import commands
from models import Player
import trade


class TradeIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.sessions = []
        for name in ('Alice', 'Bob', 'Carol'):
            self.sessions.append(NS(player=Player(name, name, room_vnum=1, ryo=100),
                                    trade=None, messages=[], account=NS(staff_level='player')))
        for session in self.sessions:
            session.send = session.messages.append
            session.active_sessions = lambda: self.sessions
        self.a, self.b, self.c = self.sessions

    def ready(self):
        result = trade.start_trade(self.a, self.b)
        result.accepted = result.confirmed_a = result.confirmed_b = True
        return result

    def balances(self):
        return [(list(s.player.inventory), s.player.ryo) for s in self.sessions]

    def test_initiator_cannot_accept_own_proposal(self):
        commands.cmd_trade(self.a, ['Bob'])
        commands.cmd_trade(self.a, ['Bob'])
        self.assertFalse(self.a.trade.accepted)
        commands.cmd_trade(self.b, ['Alice'])
        self.assertTrue(self.a.trade.accepted)

    def test_pending_proposal_cannot_be_overwritten(self):
        commands.cmd_trade(self.a, ['Bob'])
        original = self.a.trade
        commands.cmd_trade(self.c, ['Bob'])
        commands.cmd_trade(self.a, ['Carol'])
        self.assertIs(self.a.trade, original)
        self.assertIs(self.b.trade, original)
        self.assertIsNone(self.c.trade)

    def test_spending_offered_ryo_blocks_both_transfers(self):
        result = self.ready()
        result.offer_a['ryo'] = 100
        self.a.player.ryo = 20
        self.b.player.inventory = ['A Plain Stick']
        result.offer_b['items'] = ['A Plain Stick']
        before = self.balances()
        with self.assertRaisesRegex(ValueError, 'ryo'):
            trade.complete_trade(result)
        self.assertEqual(self.balances(), before)

    def test_missing_duplicate_items_never_partially_transfer(self):
        result = self.ready()
        self.a.player.inventory = ['A Plain Stick']
        result.offer_a['items'] = ['A Plain Stick', 'A Plain Stick']
        before = self.balances()
        with self.assertRaisesRegex(ValueError, 'item'):
            trade.complete_trade(result)
        self.assertEqual(self.balances(), before)

    def test_negative_offer_rejected_without_changes(self):
        result = self.ready()
        result.offer_a['ryo'] = -10
        before = self.balances()
        with self.assertRaises(ValueError):
            trade.complete_trade(result)
        self.assertEqual(self.balances(), before)

    def test_completion_requires_consent_same_room_and_current_trade(self):
        for invalid in ('accepted', 'confirmed_a', 'room', 'reference'):
            with self.subTest(invalid=invalid):
                result = self.ready()
                self.b.player.room_vnum = 1
                if invalid == 'room':
                    self.b.player.room_vnum = 2
                elif invalid == 'reference':
                    self.a.trade = None
                else:
                    setattr(result, invalid, False)
                before = self.balances()
                with self.assertRaises(ValueError):
                    trade.complete_trade(result)
                self.assertEqual(self.balances(), before)

    def test_success_conserves_items_and_money_and_cannot_replay(self):
        result = self.ready()
        self.a.player.inventory = ['A Plain Stick']
        self.b.player.inventory = ['A Plain Stone']
        result.offer_a = {'items': ['A Plain Stick'], 'ryo': 40}
        result.offer_b = {'items': ['A Plain Stone'], 'ryo': 15}
        trade.complete_trade(result)
        self.assertEqual(self.a.player.inventory, ['A Plain Stone'])
        self.assertEqual(self.b.player.inventory, ['A Plain Stick'])
        self.assertEqual((self.a.player.ryo, self.b.player.ryo), (75, 125))
        self.assertIsNone(self.a.trade)
        self.assertIsNone(self.b.trade)
        with self.assertRaises(ValueError):
            trade.complete_trade(result)

    def test_command_failure_reports_reason_and_resets_confirmations(self):
        result = self.ready()
        result.offer_a['ryo'] = 101
        commands.cmd_trade(self.b, ['confirm'])
        self.assertFalse(result.confirmed_a)
        self.assertFalse(result.confirmed_b)
        self.assertIn('ryo', self.a.messages[-1])
        self.assertEqual(self.a.messages[-1], self.b.messages[-1])


if __name__ == '__main__':
    unittest.main()
