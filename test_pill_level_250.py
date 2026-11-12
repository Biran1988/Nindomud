"""Regression tests: Bukijutsu pill strength scales to the 250 level cap."""
import unittest
from unittest.mock import patch

import commands
import consumables
import item_types
import leveling
import models
import pill_crafting
from session import Session, State


class HighLevelPillTests(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.session = Session(self.lines.append, lambda: None)
        self.session.state = State.PLAYING
        self.player = models.Player("Pillmaker", "Pillmaker", primary_class="bukijutsu", level=250)
        self.player.stamina = 1000
        self.session.player = self.player
        self.session.start_timed_action = lambda label, delay, action: action()
        self.session.is_busy = lambda: False

    def test_101_to_250_pills_are_craftable_and_persist(self):
        self.assertEqual(pill_crafting.MAX_PILL_LEVEL, leveling.MAX_LEVEL)
        for kind, label, level in (("medicine", "Medicinal", 101),
                                   ("antidote", "Antidote", 175),
                                   ("medicine", "Medicinal", 250)):
            self.player.inventory.append("Medicinal Herbs")
            commands.cmd_craft(self.session, ["pill", kind, str(level)])
            pill = pill_crafting.encode_pill(label, level)
            self.assertIn(pill, self.player.inventory)
            self.assertEqual(pill_crafting.pill_data(pill)["level"], level)
            self.assertEqual(item_types.classify_item(pill), "medical")
        saved = models.Player.from_dict(self.player.to_dict())
        self.assertEqual(saved.inventory, self.player.inventory)
        self.assertEqual(pill_crafting.pill_data(saved.inventory[-1])["amount"], 1600)

    def test_cannot_exceed_player_or_game_level(self):
        self.player.level = 120
        self.player.inventory = ["Medicinal Herbs"]
        for requested in ("121", "251", "0", "-1"):
            commands.cmd_craft(self.session, ["pill", "medicine", requested])
        self.assertEqual(self.player.inventory, ["Medicinal Herbs"])
        for level in (0, 251, 999):
            self.assertIsNone(pill_crafting.pill_data(pill_crafting.encode_pill("Medicinal", level)))

    def test_high_potency_heal_and_antidote(self):
        self.player.maximum_health = self.player.maximum_chakra = self.player.maximum_stamina = 3000
        self.player.health = self.player.chakra = self.player.stamina = 50
        self.player.inventory = [pill_crafting.encode_pill("Medicinal", 250),
                                 pill_crafting.encode_pill("Antidote", 175)]
        self.player.active_status_effects["poisoned"] = {"duration": 5}
        with patch.object(consumables.time, "time", return_value=1000):
            commands.cmd_use(self.session, ["medicinal"])
        self.assertEqual(self.player.medical_healing[0]["amount"], 1600)
        self.assertEqual(consumables.tick_medical_healing(self.player, now=1030),
                         {"health": 1600, "chakra": 1600, "stamina": 1600})
        commands.cmd_eat(self.session, ["antidote"])
        self.assertNotIn("poisoned", self.player.active_status_effects)


if __name__ == "__main__":
    unittest.main()
