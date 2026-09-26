"""Bukijutsu pill crafting, persisted potency, display and medical effects."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import commands
import consumables
import content
import item_types
import models
import olc
import pill_crafting
from session import Session, State


class PillCraftingTests(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.session = Session(self.output.append, lambda: None)
        self.session.state = State.PLAYING
        self.player = models.Player("Pillmaker", "Pillmaker", primary_class="bukijutsu", level=50)
        self.player.stamina = 500
        self.session.player = self.player
        self.session.start_timed_action = lambda label, delay, resolve: resolve()
        self.session.is_busy = lambda: False

    def test_bukijutsu_gate_and_selected_level(self):
        content._register_shared_items()
        self.assertEqual(olc.OBJECT_TEMPLATES[9809]["short_desc"], "Medicinal Herbs")
        self.player.inventory.append("Medicinal Herbs")
        self.player.primary_class = "ninjutsu"
        self.player.level = 100
        commands.cmd_craft(self.session, ["pill", "medicine", "50"])
        self.assertEqual(self.player.inventory, ["Medicinal Herbs"])
        self.player.primary_class = "bukijutsu"
        self.player.level = 50
        commands.cmd_craft(self.session, ["pill", "medicine", "51"])
        self.assertEqual(self.player.inventory, ["Medicinal Herbs"])
        commands.cmd_craft(self.session, ["pill", "medicine", "25"])
        pill = self.player.inventory[0]
        self.assertEqual(pill_crafting.display_name(pill), "Medicinal Pill")
        self.assertEqual(pill_crafting.pill_data(pill)["level"], 25)
        self.assertEqual(item_types.classify_item(pill), "medical")
        self.assertNotIn("pill_level", "".join(self.output))
        self.assertNotIn("Level 25", "".join(self.output))

        restored = models.Player.from_dict(self.player.to_dict())
        self.assertEqual(restored.inventory, self.player.inventory)
        self.session.player = restored
        restored.learned_skills.append("Examine")
        commands.cmd_examine(self.session, ["medicinal", "pill"])
        self.assertIn("Pill Level:", "".join(self.output))
        self.assertIn("25", "".join(self.output))

    def test_healing_and_antidote(self):
        self.player.maximum_health = 500
        self.player.maximum_chakra = 500
        self.player.maximum_stamina = 500
        self.player.health = self.player.chakra = self.player.stamina = 100
        self.player.inventory.extend([pill_crafting.encode_pill("Medicinal", 25),
                                      pill_crafting.encode_pill("Antidote", 30)])
        self.player.active_status_effects = {"bleeding": {}, "silenced": {}, "poisoned": {}}
        with patch.object(consumables.time, "time", return_value=1000):
            consumables.consume(self.session, "use", "medicinal")
        self.assertEqual(set(self.player.active_status_effects), {"poisoned"})
        self.assertEqual(self.player.medical_healing[0]["amount"], 250)
        self.assertEqual(consumables.tick_medical_healing(self.player, now=1030),
                         {"health": 250, "chakra": 250, "stamina": 250})
        with patch.object(consumables.time, "time", return_value=2000):
            consumables.consume(self.session, "use", "antidote")
        self.assertNotIn("poisoned", self.player.active_status_effects)
        self.assertEqual(self.player.medical_healing[0]["amount"], 110)

    def test_indexed_use_selects_individual_pill_level(self):
        first = pill_crafting.encode_pill("Medicinal", 25)
        second = pill_crafting.encode_pill("Medicinal", 50)
        self.player.inventory.extend([first, second])
        with patch.object(consumables.time, "time", return_value=1000):
            consumables.consume(self.session, "use", "2.pill")
        self.assertEqual(self.player.inventory, [first])
        self.assertEqual(self.player.medical_healing[0]["amount"], 400)


if __name__ == "__main__":
    unittest.main()
