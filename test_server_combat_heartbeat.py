"""Regression checks: Iron Ascension combat must continue on an independent heartbeat."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import iron_ascension
import server
from models import Player
from session import State


class CombatHeartbeatTests(unittest.TestCase):
    def _session(self, name, mob):
        return NS(
            player=Player(name, name, room_vnum=iron_ascension.START),
            state=State.PLAYING,
            account=NS(staff_level="implementor"),
            combat_target=mob, pvp_target=None,
            send=Mock(), send_prompt=Mock(),
        )

    def test_iron_ascension_attack_advances_on_heartbeat(self):
        """The first guardian's active target is passed to real PvE resolution."""
        guardian = NS(name="an Iron Ascension floor 1 shinobi",
                      template_vnum=iron_ascension.guardian_vnum(1),
                      room_vnum=iron_ascension.START, health=100)
        kinto = self._session("Kinto", guardian)
        kinto.combat_target = None
        with patch("groups.assist_group_attack"), \
             patch("session.ACTIVE_SESSIONS", [kinto]), \
             patch("combat.resolve_pulse") as resolve, \
             patch("susanoo.combat_upkeep", return_value=False), \
             patch("combat.tick_summon_upkeep"), \
             patch("combat.tick_ordered_summon"):
            combat.start_attack(kinto, guardian)
            self.assertIs(kinto.combat_target, guardian)
            server.tick_combat_rounds()
        resolve.assert_called_once_with(kinto, retaliate=True)
        kinto.send_prompt.assert_called()

    def test_one_character_error_does_not_freeze_another_fight(self):
        first_guardian = NS(name="iron first", template_vnum=31001)
        next_guardian = NS(name="iron second", template_vnum=31002)
        first = self._session("Kinto", first_guardian)
        second = self._session("Other", next_guardian)
        with patch("session.ACTIVE_SESSIONS", [first, second]), \
             patch("combat.resolve_pulse", side_effect=[RuntimeError("bad fight"), None]) as resolve, \
             patch("susanoo.combat_upkeep", return_value=False), \
             patch("combat.tick_summon_upkeep"), \
             patch("combat.tick_ordered_summon"), \
             patch.object(server.LOG, "exception") as log:
            server.tick_combat_rounds()
        self.assertEqual(resolve.call_count, 2)
        self.assertTrue(log.called)
        second.send_prompt.assert_called()


if __name__ == "__main__":
    unittest.main()
