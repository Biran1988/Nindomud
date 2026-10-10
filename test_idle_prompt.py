"""Paid upkeep stays quiet until it has an actual report or fades."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import server
import upkeep_reports
from models import Player


class IdlePromptTests(unittest.TestCase):
    def test_silent_sustained_jutsu_do_not_repaint_prompt(self):
        player = Player("Quiet", "Quiet", chakra=1000, maximum_chakra=1000,
                        stamina=100, maximum_stamina=100)
        player.bloodline_id = "sharingan"
        player.bloodline_tomoe = 1
        player.sharingan_active = True
        player.signed_summoning_contracts = ["toad"]
        player.sage_mastery = {"toad": 100}
        player.sage_active_contract = "toad"
        player.samurai_sabre_active = True
        player.equipment["wielded"] = "A Basic Sword"
        session = NS(player=player, send=Mock(), send_prompt=Mock())
        now = [100]
        with patch.object(upkeep_reports.time, "monotonic", side_effect=lambda: now[0]):
            server.tick_idle_upkeep(session)
            self.assertEqual(player.chakra, 978)
            session.send.assert_not_called()
            session.send_prompt.assert_not_called()

            now[0] = 461
            server.tick_idle_upkeep(session)
            self.assertEqual(session.send.call_count, 1)
            session.send_prompt.assert_called_once()
            self.assertIn("Upkeep total:", session.send.call_args.args[0])

            session.send.reset_mock()
            session.send_prompt.reset_mock()
            player.chakra = 0
            now[0] = 471
            server.tick_idle_upkeep(session)
            self.assertGreater(session.send.call_count, 0)
            session.send_prompt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
