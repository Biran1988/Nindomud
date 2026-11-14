"""Double food recovery without increasing medicine or drinks."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import consumables
import farming
import seasonal_events
import halloween_event
from models import Player


class FoodRecoveryRebalanceTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("FoodTest", "FoodTest")
        self.player.maximum_stamina = 10000
        self.player.maximum_health = self.player.maximum_chakra = 10000
        self.player.stamina = self.player.health = self.player.chakra = 0
        self.messages = []
        self.session = SimpleNamespace(player=self.player, send=self.messages.append)

    def eat(self, name):
        self.player.inventory = [name]
        consumables.consume(self.session, "eat", name)
        self.assertEqual(self.player.inventory, [])

    def test_base_food_doubled_and_leviathan_exact_5000(self):
        for name, base in (("A Rice Ball", 25), ("A Bowl of Ramen", 40),
                           ("A Cooked Salmon", 55), ("A Cooked Golden Koi", 80)):
            with self.subTest(name=name):
                self.player.stamina = 0
                self.eat(name)
                self.assertEqual(self.player.stamina, base * 2)
        self.player.stamina = 0
        self.eat("A Leviathan Fillet")
        self.assertEqual(self.player.stamina, 5000)

    def test_raw_and_cooked_farm_foods_all_doubled(self):
        for raw, rec in farming.EDIBLE_CROPS.items():
            for name, base in ((raw, rec["raw_stamina"]),
                               (rec["dish"], rec["cooked_stamina"])):
                with self.subTest(name=name):
                    self.player.stamina = 0
                    self.eat(name)
                    self.assertEqual(self.player.stamina, base * 2)

    def test_leviathan_respects_max_stamina(self):
        self.player.maximum_stamina = 3000
        self.player.stamina = 100
        self.eat("A Leviathan Fillet")
        self.assertEqual(self.player.stamina, 3000)

    def test_drinks_and_medical_healing_unchanged(self):
        self.player.inventory = ["A Canteen of Water"]
        consumables.consume(self.session, "drink", "water")
        self.assertEqual(self.player.chakra, 20)
        self.player.inventory = ["A Healing Salve"]
        consumables.consume(self.session, "use", "salve")
        self.assertEqual(self.player.medical_healing[-1]["amount"], 35)

    def test_seasonal_meals_also_doubled(self):
        self.player.inventory = [seasonal_events.BOMB_POP, seasonal_events.BBQ_FOOD]
        with patch.object(seasonal_events.storage, "save_player"):
            self.assertTrue(seasonal_events.eat_july_fourth_food(self.session, "popsicle"))
            self.assertEqual(self.player.stamina, 120)
            self.assertEqual(self.player.chakra, 120)
            self.assertTrue(seasonal_events.eat_july_fourth_food(self.session, "bbq"))
            self.assertEqual(self.player.stamina, 320)
            self.assertEqual(self.player.health, 200)


if __name__ == "__main__":
    unittest.main()
