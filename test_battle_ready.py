"""Battle Ready customization, persistence and safe buff activation."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import battle_ready
import commands
import status_effects
from models import Player


class BattleReadyTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Kakashi", "Kakashi", primary_class="bukijutsu", level=100)
        self.player.chakra = 1000
        self.player.stamina = 1000
        self.player.health = 1000
        self.out = []
        self.session = SimpleNamespace(
            player=self.player, send=self.out.append, pending_cast=None,
            pending_action=None, combat_target=None, pvp_target=None,
            is_busy=lambda: False,
        )

    def test_initial_default_choices_and_per_character_persistence(self):
        cfg = battle_ready.settings(self.player)
        self.assertTrue(cfg["barrier"])
        self.assertTrue(cfg["focused mind"])
        self.assertTrue(cfg["sensory detect"])
        self.assertTrue(cfg["samurai sabre"])
        self.assertFalse(cfg["susanoo"])
        self.assertFalse(cfg["chisei"])
        with patch("storage.save_player") as save:
            battle_ready.command(self.session, ["ready", "samurai", "sabre", "off"])
            battle_ready.command(self.session, ["config", "sharingan", "on"])
        self.assertFalse(battle_ready.settings(self.player)["samurai sabre"])
        self.assertTrue(battle_ready.settings(self.player)["sharingan"])
        self.assertEqual(save.call_count, 2)
        restored = Player.from_dict(self.player.to_dict())
        self.assertFalse(battle_ready.settings(restored)["samurai sabre"])
        self.assertTrue(battle_ready.settings(restored)["sharingan"])

    def test_config_command_works_under_normal_preferences(self):
        with patch("storage.save_player") as save:
            commands.cmd_config(self.session, ["battle", "ready", "focused", "mind", "off"])
            commands.cmd_config(self.session, ["battle_ready", "sensory", "detect", "off"])
        self.assertFalse(battle_ready.settings(self.player)["focused mind"])
        self.assertFalse(battle_ready.settings(self.player)["sensory detect"])
        self.assertEqual(save.call_count, 2)
        commands.cmd_config(self.session, ["battle", "ready"])
        self.assertTrue(any("Battle Ready configuration" in msg for msg in self.out))

    def test_unlearned_buffs_not_cast_and_already_active_never_retoggle(self):
        # The initial configuration selects four skills. Focus is already on.
        status_effects.apply_effect(self.player.active_status_effects, "focused_mind",
                                    source="focused mind", duration_override=120)
        casted = []
        def cast(sess, key):
            casted.append(key)
            if key == "barrier":
                status_effects.apply_effect(self.player.active_status_effects, "barrier",
                                            source="barrier", duration_override=180)
            if key == "sensory detect":
                status_effects.apply_effect(self.player.active_status_effects, "sensory_detect",
                                            source=key, duration_override=120)
        with (patch.object(battle_ready, "_available",
                           side_effect=lambda p, key: key in ("barrier", "focused mind", "sensory detect")),
              patch.object(battle_ready, "_cast", side_effect=cast)):
            battle_ready.command(self.session, ["ready"])
            battle_ready.command(self.session, ["ready"])
        self.assertEqual(casted, ["barrier", "sensory detect"])
        self.assertTrue(any("Already active" in text for text in self.out))

    def test_config_save_failure_reverts_toggles(self):
        with patch("storage.save_player", side_effect=OSError("disk full")):
            battle_ready.command(self.session, ["ready", "barrier", "off"])
        self.assertTrue(battle_ready.settings(self.player)["barrier"])
        self.assertTrue(any("Unable to save" in msg for msg in self.out))

    def test_preparation_rejects_blocked_or_pending_action(self):
        self.session.pending_cast = object()
        with patch.object(battle_ready, "_cast") as cast:
            battle_ready.command(self.session, ["ready"])
        cast.assert_not_called()
        self.assertTrue(any("current action" in msg for msg in self.out))

    def test_already_active_sabre_is_not_toggled_off(self):
        self.player.samurai_sabre_active = True
        with (patch.object(battle_ready, "_available", return_value=True),
              patch.object(battle_ready, "_cast") as cast):
            battle_ready.command(self.session, ["ready"])
        self.assertNotIn("samurai sabre", [x.args[1] for x in cast.call_args_list])
        self.assertTrue(self.player.samurai_sabre_active)

    def test_help_description_registered(self):
        import help_system
        pages = [p for p in help_system.DEFAULT_HELP_ENTRIES
                 if p["primary_keyword"] == "battle ready"]
        self.assertEqual(len(pages), 1)
        self.assertIn("config battle ready", pages[0]["body"])


if __name__ == "__main__":
    unittest.main()
