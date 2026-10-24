"""Explicit tail selection preserves availability, permissions and random mode."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import combat
import commands
import data_tailed_beasts
import tailed_beasts
import world


class UnleashSelectionTests(unittest.TestCase):
    def setUp(self):
        for item in (patch.object(combat, "MOBS_BY_ROOM", {}),
                     patch.object(combat, "MOB_TEMPLATES", {}),
                     patch.object(world.WORLD, "rooms", {992880: world.Room(992880, "Wilds", "Open land.")}),
                     patch("storage.all_players", return_value=[]),
                     patch.object(commands, "_broadcast_globally")):
            item.start()
            self.addCleanup(item.stop)
        tailed_beasts.register_all_beast_templates(combat)
        self.s = NS(player=NS(name="Staff", jinchuriki_beast_key=None),
                    account=NS(staff_level="implementor"), send=Mock())
        self.s.active_sessions = lambda: [self.s]

    def test_each_tail_count_selects_correct_actual_beast(self):
        for beast in data_tailed_beasts.TAILED_BEASTS:
            with self.subTest(tails=beast["tails"]):
                combat.MOBS_BY_ROOM.clear()
                commands.cmd_unleash(self.s, ["beast", str(beast["tails"])])
                mob = combat.mobs_in_room(992880)[0]
                self.assertEqual(mob.tailed_beast_key, beast["key"])
                self.assertIn(beast["display_name"], commands._broadcast_globally.call_args.args[0])

    def test_omitted_number_stays_random_and_roaming_cap_still_blocks(self):
        beast = data_tailed_beasts.TAILED_BEASTS[3]
        with patch.object(tailed_beasts, "pick_random_available_beast", return_value=beast) as choose:
            commands.cmd_unleash(self.s, ["beast"])
            choose.assert_called_once()
        self.assertEqual(combat.mobs_in_room(992880)[0].tailed_beast_key, beast["key"])
        commands.cmd_unleash(self.s, ["beast", "2"])
        self.assertEqual(len(combat.mobs_in_room(992880)), 1)
        self.assertIn("already loose", self.s.send.call_args.args[0])

    def test_offline_holder_blocks_selected_beast_without_reroll(self):
        with patch("storage.all_players", return_value=[NS(name="Offline", jinchuriki_beast_key="matatabi")]):
            commands.cmd_unleash(self.s, ["beast", "2"])
        self.assertEqual(combat.mobs_in_room(992880), [])
        self.assertIn("Matatabi is already sealed", self.s.send.call_args.args[0])
        commands._broadcast_globally.assert_not_called()

    def test_invalid_numbers_and_non_staff_cannot_spawn(self):
        for words in (["beast", "0"], ["beast", "10"], ["beast", "two"],
                      ["beast", "2", "extra"], ["beast", "-1"]):
            commands.cmd_unleash(self.s, words)
            self.assertIn("Usage:", self.s.send.call_args.args[0])
        self.s.account.staff_level = "player"
        commands.cmd_unleash(self.s, ["beast", "2"])
        self.assertEqual(combat.mobs_in_room(992880), [])


if __name__ == "__main__":
    unittest.main()
