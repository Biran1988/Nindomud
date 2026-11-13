"""Saved damage-number preference with independently rendered viewer output."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import damage_messages
from models import Player


class DamageDisplayConfigTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("DamageTester", "DamageTester")
        self.session = NS(player=self.player, send=Mock())

    def test_default_words_and_numbers_survive_reload(self):
        self.assertFalse(self.player.damage_numbers)
        self.assertIn("CRUSHING", damage_messages.describe_damage(150, self.player))
        with patch("storage.save_player") as save:
            commands.cmd_config(self.session, ["damage", "numbers"])
        save.assert_called_once_with(self.player)
        self.assertTrue(self.player.damage_numbers)
        self.assertEqual(damage_messages.describe_damage(150, self.player), "150")
        self.assertEqual(damage_messages.describe_damage(12345, self.player), "12,345")
        self.assertIn("CRUSHING", damage_messages.describe_damage(150))
        reloaded = Player.from_dict(self.player.to_dict())
        self.assertTrue(reloaded.damage_numbers)
        with patch("storage.save_player"):
            commands.cmd_config(self.session, ["damage", "words"])
        self.assertFalse(self.player.damage_numbers)
        self.assertIn("CRUSHING", damage_messages.describe_damage(150, self.player))

    def test_mode_is_per_viewer_and_invalid_options_dont_save(self):
        second = Player("Other", "Other")
        self.player.damage_numbers = True
        self.assertEqual(damage_messages.describe_damage(53, self.player), "53")
        self.assertIn("THUNDEROUS", damage_messages.describe_damage(53, second))
        with patch("storage.save_player") as save:
            commands.cmd_config(self.session, ["damage", "incorrect"])
        save.assert_not_called()
        self.assertIn("config damage numbers|words", self.session.send.call_args.args[0])

    def test_save_failure_restores_preference(self):
        with patch("storage.save_player", side_effect=OSError("offline")):
            commands.cmd_config(self.session, ["damage", "numbers"])
        self.assertFalse(self.player.damage_numbers)
        self.assertIn("Unable to save", self.session.send.call_args.args[0])

    def test_config_listing_includes_mode(self):
        commands.cmd_config(self.session, [])
        self.assertIn("damage", self.session.send.call_args.args[0])
        self.assertIn("words", self.session.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
