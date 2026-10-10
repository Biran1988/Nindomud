"""Chakra Charge grant, conversion, and clone upkeep accounting."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import combat
import commands
import data_jutsu
import leveling
from models import Player


class ChakraChargeTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Charger", "Charger", level=10, chakra=0,
                             maximum_chakra=99, stamina=50, maximum_stamina=50)
        self.session = SimpleNamespace(player=self.player, send=Mock(), send_prompt=Mock(),
                                       chakra_charge=None, pending_cast=None, is_busy=lambda: False)

    def test_unlock_at_level_ten_and_sync_for_returning_character(self):
        self.assertNotIn("Chakra Charge", data_jutsu.UNIVERSAL_STARTING_SKILLS)
        self.player.level = 9
        leveling.sync_universal_skills(self.player)
        self.assertNotIn("Chakra Charge", self.player.learned_skills)
        self.player.level = 10
        leveling.sync_universal_skills(self.player)
        self.assertIn("Chakra Charge", self.player.learned_skills)
        self.assertEqual(commands._skill_unlock_level("Chakra Charge"), 10)

    def test_selected_amount_flows_in_fifths_every_four_seconds(self):
        self.player.learned_skills.append("Chakra Charge")
        with patch.object(commands.time, "time", return_value=1000):
            commands.cmd_charge(self.session, ["10"])
        self.assertEqual((self.player.stamina, self.player.chakra), (50, 0))
        commands.process_chakra_charge(self.session, now=1003.9)
        self.assertEqual((self.player.stamina, self.player.chakra), (50, 0))
        for step in range(1, 6):
            commands.process_chakra_charge(self.session, now=1000 + step * 4)
            self.assertEqual((self.player.stamina, self.player.chakra), (50 - step * 2, step * 4))
        self.assertIsNone(self.session.chakra_charge)
        self.session.send_prompt.assert_called_once()

    def test_fractional_fifths_carry_and_default_fills_chakra(self):
        self.player.learned_skills.append("Chakra Charge")
        with patch.object(commands.time, "time", return_value=1000):
            commands.cmd_charge(self.session, ["3"])
        expected_spent = [0, 1, 1, 2, 3]
        for step, spent in enumerate(expected_spent, 1):
            commands.process_chakra_charge(self.session, now=1000 + step * 4)
            self.assertEqual((self.player.stamina, self.player.chakra), (50 - spent, 2 * spent))
        with patch.object(commands.time, "time", return_value=2000):
            commands.cmd_charge(self.session, [])
        self.assertEqual((self.player.stamina, self.player.chakra), (47, 6))
        commands.process_chakra_charge(self.session, now=2020)
        self.assertEqual((self.player.stamina, self.player.chakra), (0, 99))
        self.session.send.assert_called_with("&CChakra Charge finishes: 47 Stamina became 93 Chakra.&x")

    def test_full_chakra_empty_stamina_and_bad_amount_spend_nothing(self):
        self.player.learned_skills.append("Chakra Charge")
        for args in (["0"], ["-1"], ["foo"], ["1", "2"]):
            commands.cmd_charge(self.session, args)
            self.assertEqual((self.player.chakra, self.player.stamina), (0, 50))
        self.player.chakra = 99
        commands.cmd_charge(self.session, [])
        self.assertEqual(self.player.stamina, 50)
        self.player.chakra = 0
        self.player.stamina = 0
        commands.cmd_charge(self.session, [])
        self.assertEqual(self.player.chakra, 0)

    def test_near_cap_uses_only_one_stamina(self):
        self.player.learned_skills.append("Chakra Charge")
        self.player.chakra = 98
        with patch.object(commands.time, "time", return_value=1000):
            commands.cmd_charge(self.session, ["5"])
        self.assertEqual((self.player.chakra, self.player.stamina), (98, 50))
        commands.process_chakra_charge(self.session, now=1020)
        self.assertEqual((self.player.chakra, self.player.stamina), (99, 49))

    def test_stop_and_sleep_interrupt_without_future_cost(self):
        self.player.learned_skills.append("Chakra Charge")
        with patch.object(commands.time, "time", return_value=1000):
            commands.cmd_charge(self.session, ["10"])
        commands.process_chakra_charge(self.session, now=1004)
        commands.cmd_charge(self.session, ["stop"])
        commands.process_chakra_charge(self.session, now=1020)
        self.assertEqual((self.player.stamina, self.player.chakra), (48, 4))
        with patch.object(commands.time, "time", return_value=2000):
            commands.cmd_charge(self.session, ["10"])
        self.player.position = "sleeping"
        commands.process_chakra_charge(self.session, now=2004)
        self.assertEqual((self.player.stamina, self.player.chakra), (48, 4))
        self.assertIsNone(self.session.chakra_charge)


class CloneUpkeepTests(unittest.TestCase):
    def test_one_clone_charges_exactly_fifteen_chakra_across_four_pulses(self):
        player = Player("CloneCost", "CloneCost", chakra=100, maximum_chakra=100)
        clone = SimpleNamespace(shadow_clone_owner=player.name, room_vnum=999999,
                                clone_element="none")
        combat.MOBS_BY_ROOM.setdefault(clone.room_vnum, []).append(clone)
        try:
            costs = []
            for _ in range(4):
                previous = player.chakra
                combat.tick_shadow_clone_upkeep(player)
                costs.append(previous - player.chakra)
            self.assertEqual(costs, [3, 4, 4, 4])
            self.assertEqual(player.chakra, 85)
        finally:
            combat.MOBS_BY_ROOM[clone.room_vnum].remove(clone)


if __name__ == "__main__":
    unittest.main()
