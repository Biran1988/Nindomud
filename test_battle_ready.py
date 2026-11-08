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

    def test_real_one_command_activation_uses_actual_resources_and_does_not_toggle_off(self):
        import combat
        import data_jutsu
        import skill_training
        from session import Session, State, ACTIVE_SESSIONS
        p = Player("Prepared", "Prepared", level=50, primary_class="bukijutsu")
        p.maximum_chakra = p.chakra = 5000
        p.maximum_stamina = p.stamina = 5000
        p.equipment["wielded"] = "A Basic Sword"
        p.practice_gate_enabled = True
        for key in ("barrier", "focused mind", "sensory detect", "samurai sabre"):
            spec = data_jutsu.JUTSU[key]
            p.learned_skills.append(spec["display_name"])
            p.skill_proficiencies[spec["display_name"]] = 50
            skill_training.mark_practiced(p, spec["display_name"])
        lines = []
        live = Session(lines.append, lambda: None)
        live.state = State.PLAYING
        live.player = p
        try:
            with (patch.object(combat, "grow_skill_from_usage"),
                  patch("storage.save_player")):
                battle_ready.command(live, ["ready"])
            self.assertTrue(status_effects.has_effect(p.active_status_effects, "barrier"))
            self.assertTrue(status_effects.has_effect(p.active_status_effects, "focused_mind"))
            self.assertTrue(status_effects.has_effect(p.active_status_effects, "sensory_detect"))
            self.assertTrue(p.samurai_sabre_active)
            self.assertLess(p.chakra, 5000)
            spent_chakra, spent_stamina = p.chakra, p.stamina
            battle_ready.command(live, ["ready"])
            self.assertEqual((p.chakra, p.stamina), (spent_chakra, spent_stamina))
            self.assertTrue(p.samurai_sabre_active)
        finally:
            if live in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS.remove(live)


    def test_additional_jutsu_options_start_disabled_and_save_per_character(self):
        additional = (
            "hidden mist jutsu", "six paths mode", "tailed beast mode", "bijuu cloak",
            "celestial byakugan", "tenseigan chakra mode", "kamui intangibility",
            "sanchin dachi", "neko ashi dachi", "kihon dachi",
        )
        original_defaults = {"barrier", "focused mind", "sensory detect", "samurai sabre"}
        settings = battle_ready.settings(self.player)
        self.assertEqual({k for k, v in settings.items() if v}, original_defaults)
        for key in additional:
            self.assertIn(key, settings)
            self.assertFalse(settings[key], key)
        with patch("storage.save_player"):
            battle_ready.command(self.session, ["ready", "hidden", "mist", "jutsu", "on"])
            commands.cmd_config(self.session, ["battle", "ready", "sixpaths", "on"])
            battle_ready.command(self.session, ["ready", "sanchin", "dachi", "on"])
        restored = Player.from_dict(self.player.to_dict())
        self.assertTrue(battle_ready.settings(restored)["hidden mist jutsu"])
        self.assertTrue(battle_ready.settings(restored)["six paths mode"])
        self.assertTrue(battle_ready.settings(restored)["sanchin dachi"])

    def test_advanced_jutsu_use_real_commands_not_free_effects(self):
        import bijuu_chakra
        import hyuga
        import six_paths
        with (patch.object(commands, "cmd_use_jutsu") as perform,
              patch.object(commands, "cmd_tailed_beast_mode") as beast,
              patch.object(hyuga, "cast") as bloodline,
              patch.object(six_paths, "command") as six,
              patch.object(bijuu_chakra, "command") as bijuu):
            battle_ready._cast(self.session, "hidden mist jutsu")
            perform.assert_called_with(self.session, "hidden mist jutsu", ["on"])
            battle_ready._cast(self.session, "sanchin dachi")
            perform.assert_called_with(self.session, "sanchin dachi", [])
            battle_ready._cast(self.session, "kamui intangibility")
            perform.assert_called_with(self.session, "kamui intangibility", [])
            battle_ready._cast(self.session, "celestial byakugan")
            bloodline.assert_called_with(self.session, "celestial byakugan", ["on"])
            battle_ready._cast(self.session, "tenseigan chakra mode")
            bloodline.assert_called_with(self.session, "tenseigan chakra mode", ["on"])
            battle_ready._cast(self.session, "six paths mode")
            six.assert_called_with(self.session, ["on"])
            battle_ready._cast(self.session, "tailed beast mode")
            beast.assert_called_with(self.session, [])
            battle_ready._cast(self.session, "bijuu cloak")
            bijuu.assert_called_with(self.session, ["cloak"])

    def test_existing_stance_never_replaced(self):
        self.player.battle_ready_settings = {
            "sanchin dachi": True, "kihon dachi": True,
        }
        self.player.taijutsu_stance = "neko ashi dachi"
        with (patch.object(battle_ready, "_available", return_value=True),
              patch.object(battle_ready, "_cast") as cast):
            battle_ready.command(self.session, ["ready"])
        self.assertEqual(self.player.taijutsu_stance, "neko ashi dachi")
        self.assertFalse(any(x.args[1] in ("sanchin dachi", "kihon dachi")
                             for x in cast.call_args_list))

    def test_only_one_enabled_stance_starts_highest_first(self):
        self.player.battle_ready_settings = {
            "sanchin dachi": True, "kihon dachi": True,
        }
        self.player.taijutsu_stance = ""
        used = []
        def cast(session, key):
            used.append(key)
            if key == "sanchin dachi":
                self.player.taijutsu_stance = key
        with (patch.object(battle_ready, "_available",
                           side_effect=lambda player, key: key.endswith("dachi")),
              patch.object(battle_ready, "_cast", side_effect=cast)):
            battle_ready.command(self.session, ["ready"])
        self.assertEqual(used, ["sanchin dachi"])

    def test_delayed_jutsu_stops_before_another_delayed_cast(self):
        self.player.battle_ready_settings = {
            "chisei": True, "hidden mist jutsu": True,
        }
        attempted = []
        def cast(session, key):
            attempted.append(key)
            if key == "chisei":
                self.session.pending_cast = object()
        with (patch.object(battle_ready, "_available",
                           side_effect=lambda player, key: key in ("chisei", "hidden mist jutsu")),
              patch.object(battle_ready, "_cast", side_effect=cast)):
            battle_ready.command(self.session, ["ready"])
        self.assertEqual(attempted, ["chisei"])
        self.assertTrue(any("forming hand signs" in line for line in self.out))
        self.assertTrue(any("BATTLE READY again" in line for line in self.out))

    def test_modes_do_not_overwrite_stronger_bijuu_form(self):
        self.player.bijuu_form = 4
        self.assertTrue(battle_ready._active(self.player, "bijuu cloak"))
        self.player.bijuu_form = 0
        self.assertFalse(battle_ready._active(self.player, "bijuu cloak"))
        self.player.six_paths_active = True
        self.assertTrue(battle_ready._active(self.player, "six paths mode"))
        self.player.kamui_intangibility_rounds_left = 3
        self.assertTrue(battle_ready._active(self.player, "kamui intangibility"))

    def test_help_description_registered(self):
        import help_system
        pages = [p for p in help_system.DEFAULT_HELP_ENTRIES
                 if p["primary_keyword"] == "battle ready"]
        self.assertEqual(len(pages), 1)
        self.assertIn("config battle ready", pages[0]["body"])


if __name__ == "__main__":
    unittest.main()
