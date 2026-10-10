"""Sharingan spends at the normal rate but reports combined totals sparingly."""

import unittest
from unittest.mock import patch

import combat
import commands
import regen
import upkeep_reports
from models import Player


class SharinganSummaryTests(unittest.TestCase):
    def test_combines_combat_and_idle_costs_at_six_minutes(self):
        player = Player("Sharin", "Sharin")
        player.sharingan_active = True
        player.bloodline_tomoe = 1
        player.chakra = 500
        player.stamina = 100
        with patch.object(upkeep_reports.time, "monotonic", side_effect=[100, 110, 461]):
            self.assertEqual(regen.tick_sharingan_idle(player), [])
            self.assertEqual(combat.tick_sharingan_upkeep(player), [])
            self.assertEqual(regen.tick_sharingan_idle(player), [
                "&CUpkeep total: Sharingan 24 Chakra, 6 Stamina (combined 24 Chakra, 6 Stamina).&x"
            ])
        self.assertEqual(player.chakra, 476)
        self.assertEqual(player.stamina, 94)
        self.assertEqual(upkeep_reports.flush(player), [])

    def test_fade_reports_pending_cost_once(self):
        player = Player("Sharin", "Sharin")
        player.sharingan_active = True
        player.bloodline_tomoe = 1
        player.chakra = 6
        self.assertEqual(regen.tick_sharingan_idle(player), [])
        messages = regen.tick_sharingan_idle(player)
        self.assertEqual(player.chakra, 0)
        self.assertEqual(player.sharingan_active, False)
        self.assertIn("Sharingan upkeep total: 6 Chakra", messages[0])
        self.assertIn("fades back to black", messages[1])
        self.assertEqual(upkeep_reports.flush(player), [])

    def test_manual_toggle_reports_pending_cost(self):
        player = Player("Sharin", "Sharin")
        player.sharingan_active = True
        player.bloodline_id = "sharingan"
        player.bloodline_tomoe = 1
        player.chakra = 100
        regen.tick_sharingan_idle(player)
        class Session:
            pass
        session = Session()
        session.player = player
        session.messages = []
        session.send = session.messages.append
        commands.cmd_sharingan(session, [])
        self.assertEqual(player.sharingan_active, False)
        self.assertIn("Sharingan upkeep total: 6 Chakra", session.messages[0])
        self.assertEqual(upkeep_reports.flush(player), [])


if __name__ == "__main__":
    unittest.main()
