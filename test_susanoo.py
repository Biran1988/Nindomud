"""Universal Mangekyo Susanoo, SET SUSANOO menu, combat bonuses and saves."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import combat
import data_mangekyo
import help_system
import olc
import susanoo
from models import Player


class SusanooTests(unittest.TestCase):
    def setUp(self):
        self.p = Player("Guardian", "Guardian", primary_class="genjutsu",
                        level=200, chakra=400, maximum_chakra=500)
        self.p.bloodline_id = "sharingan"
        self.p.bloodline_awakened = True
        self.p.bloodline_mangekyo = True
        self.p.mangekyo_eye_1 = "kamui"
        self.p.mangekyo_eye_2 = "izanagi"
        self.s = NS(player=self.p, send=Mock(), combat_target=None,
                    pvp_target=None, send_prompt=Mock())
        self.saves = []
        patcher = patch.object(susanoo.storage, "save_player",
                               side_effect=lambda p: self.saves.append(json.loads(json.dumps(p.to_dict()))))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_mangekyo_holder_has_it_without_eye_roll(self):
        for first, second in (("kamui", "izanagi"), ("tsukuyomi", "amaterasu"),
                              ("izanami", "kekkei_no_me")):
            with self.subTest(first=first):
                self.p.mangekyo_eye_1, self.p.mangekyo_eye_2 = first, second
                self.assertTrue(susanoo.eligible(self.p))
                with patch("room_actions.emit"):
                    susanoo.command(self.s, ["on"])
                self.assertTrue(self.p.susanoo_active)
                self.assertEqual((self.p.mangekyo_eye_1, self.p.mangekyo_eye_2), (first, second))
                susanoo.command(self.s, ["off"])
                self.assertFalse(self.p.susanoo_active)
        self.p.bloodline_mangekyo = False
        self.assertFalse(susanoo.eligible(self.p))
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 100)
        self.s.send.reset_mock()
        susanoo.command(self.s, ["on"])
        self.assertIn("Mangekyo", self.s.send.call_args.args[0])

    def test_set_susanoo_menu_displays_saved_selections(self):
        commands.COMMANDS["set"](self.s, ["susanoo"])
        displayed = self.s.send.call_args.args[0]
        for name in ("Color:", "Style:", "Weapon:", "Purple", "Balanced", "Sword"):
            self.assertIn(name, displayed)
        commands.COMMANDS["set"](self.s, ["susanoo", "color", "blue"])
        commands.COMMANDS["set"](self.s, ["susanoo", "style", "defensive"])
        commands.COMMANDS["set"](self.s, ["susanoo", "weapon", "shield"])
        self.assertEqual((self.p.susanoo_color, self.p.susanoo_style, self.p.susanoo_weapon),
                         ("blue", "defensive", "shield"))
        restored = Player.from_dict(self.saves[-1])
        self.assertEqual((restored.susanoo_color, restored.susanoo_style, restored.susanoo_weapon),
                         ("blue", "defensive", "shield"))
        self.s.send.reset_mock()
        susanoo.command_set(self.s, ["susanoo", "menu"])
        view = self.s.send.call_args.args[0]
        self.assertIn("Blue", view)
        self.assertIn("Defensive", view)
        self.assertIn("Shield", view)

    def test_weapon_menu_and_validation(self):
        susanoo.command_set(self.s, ["susanoo", "weapons"])
        for weapon in ("sword", "shield", "bow", "dagger", "spear", "axe", "staff", "mace"):
            self.assertIn(weapon, self.s.send.call_args.args[0])
        before = len(self.saves)
        susanoo.command_set(self.s, ["susanoo", "color", "&RINVALID"])
        self.assertEqual(self.p.susanoo_color, "purple")
        self.assertEqual(len(self.saves), before)
        self.s.combat_target = object()
        susanoo.command_set(self.s, ["susanoo", "weapon", "bow"])
        self.assertEqual(self.p.susanoo_weapon, "sword")
        self.s.combat_target = None
        susanoo.command_set(self.s, ["susanoo", "weapon", "bow"])
        self.assertEqual(self.p.susanoo_weapon, "bow")

    def test_style_and_weapon_affect_melee_accuracy_and_incoming_damage(self):
        self.p.susanoo_active = True
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 122)
        self.assertEqual(susanoo.incoming_damage(self.p, 100), 85)
        self.p.susanoo_style = "defensive"
        self.p.susanoo_weapon = "shield"
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 105)
        self.assertEqual(susanoo.incoming_damage(self.p, 100), 65)
        self.p.susanoo_style = "offensive"
        self.p.susanoo_weapon = "axe"
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 140)
        self.assertEqual(susanoo.incoming_damage(self.p, 100), 95)
        self.assertEqual(susanoo.accuracy_bonus(self.p), -3)
        self.p.susanoo_weapon = "bow"
        self.assertEqual(susanoo.accuracy_bonus(self.p), 12)
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 125)
        self.p.susanoo_weapon = "dagger"
        self.assertEqual(susanoo.accuracy_bonus(self.p), 8)
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 130)
        self.p.susanoo_weapon = "spear"
        self.assertEqual(susanoo.accuracy_bonus(self.p), 6)
        self.p.susanoo_weapon = "staff"
        self.assertEqual(susanoo.incoming_damage(self.p, 100), 90)
        self.p.susanoo_weapon = "mace"
        self.assertEqual(susanoo.accuracy_bonus(self.p), -2)
        self.p.susanoo_active = False
        self.assertEqual(susanoo.outgoing_damage(self.p, 100), 100)
        self.assertEqual(susanoo.incoming_damage(self.p, 100), 100)

    def test_activation_and_upkeep_exhaust_chakra_without_negative_values(self):
        self.p.chakra = 39
        susanoo.command(self.s, ["on"])
        self.assertFalse(self.p.susanoo_active)
        self.assertEqual(self.p.chakra, 39)
        self.p.chakra = 70
        with patch("room_actions.emit"):
            commands.COMMANDS["susanoo"](self.s, ["on"])
        self.assertEqual(self.p.chakra, 30)
        self.assertTrue(self.p.susanoo_active)
        self.assertFalse(susanoo.combat_upkeep(self.s))
        self.assertEqual(self.p.chakra, 12)
        self.assertFalse(susanoo.idle_upkeep(self.s))
        self.assertEqual(self.p.chakra, 4)
        self.assertTrue(susanoo.combat_upkeep(self.s))
        self.assertEqual(self.p.chakra, 4)
        self.assertFalse(self.p.susanoo_active)
        self.assertIn("shatters", self.s.send.call_args.args[0])
        self.assertFalse(susanoo.combat_upkeep(self.s))
        self.assertEqual(self.p.chakra, 4)
        self.assertFalse(susanoo.idle_upkeep(self.s))

    def test_melee_combat_damage_uses_active_susanoo(self):
        self.p.susanoo_active = False
        with patch.object(combat.random, "randint", return_value=3):
            normal = combat._player_attack_damage(self.p)
        self.p.susanoo_active = True
        with patch.object(combat.random, "randint", return_value=3):
            empowered = combat._player_attack_damage(self.p)
        self.assertGreater(empowered, normal)

    def test_bloodset_disables_form_but_keeps_customizations(self):
        self.p.susanoo_active = True
        self.p.susanoo_color = "gold"
        self.p.susanoo_style = "offensive"
        self.p.susanoo_weapon = "bow"
        with patch.object(olc, "storage", susanoo.storage):
            olc._set_player_mangekyo(self.p, False)
        self.assertFalse(self.p.susanoo_active)
        self.assertFalse(susanoo.active(self.p))
        self.assertEqual((self.p.susanoo_color, self.p.susanoo_style, self.p.susanoo_weapon),
                         ("gold", "offensive", "bow"))
        with patch.object(data_mangekyo, "roll_two_eye_techniques", return_value=("tsukuyomi", "amaterasu")):
            olc._set_player_mangekyo(self.p, True)
        self.assertTrue(susanoo.eligible(self.p))
        self.assertEqual(self.p.susanoo_weapon, "bow")
        self.assertFalse(self.p.susanoo_active)

    def test_help_entries_are_player_accessible(self):
        for topic in ("susanoo", "set"):
            entries = [e for e in help_system.DEFAULT_HELP_ENTRIES if e["primary_keyword"] == topic]
            self.assertEqual(len(entries), 1)
            self.assertIn("set susanoo", entries[0]["body"].lower())


if __name__ == "__main__":
    unittest.main()
