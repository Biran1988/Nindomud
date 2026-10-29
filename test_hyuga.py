"""Hyuga Byakugan inheritance, progression and combat integration regression tests."""
import unittest
from unittest.mock import patch

import data_kekkei_genkai as kkg
import hyuga
import data_jutsu
import commands
from models import Player


def hyuga_player(potential=40, mastery=0, level=250, awakened=True):
    player = Player(name="Neji", account_name="Neji")
    player.clan = "hyuga"
    player.village = "leaf"
    player.primary_class = "taijutsu"
    player.level = level
    player.bloodline_id = "byakugan"
    player.bloodline_awakened = awakened
    player.bloodline_potential = potential
    player.bloodline_talent = 67
    player.bloodline_mastery = mastery
    player.chakra = player.maximum_chakra = 3000
    player.stamina = player.maximum_stamina = 1500
    return player


class HyugaTests(unittest.TestCase):

    def test_every_new_hyuga_inherits_but_other_clans_do_not(self):
        self.assertEqual(kkg.CLAN_INHERITANCE["hyuga"]["byakugan"], 1.0)
        with patch.object(kkg.random, "random", return_value=0.99999):
            result = kkg.roll_inheritance("hyuga")
        self.assertEqual(result["bloodline_id"], "byakugan")
        self.assertGreater(result["potential"], 0)
        self.assertGreater(result["talent"], 0)
        self.assertIsNone(kkg.roll_inheritance("nara")["bloodline_id"])

    def test_existing_hyuga_migrated_once_without_rerolling(self):
        p = Player("OlderHyuga", "OlderHyuga")
        p.clan = "hyuga"
        with patch.object(kkg.random, "randint", side_effect=[27, 54]):
            self.assertTrue(kkg.ensure_hyuga_inheritance(p))
        self.assertEqual((p.bloodline_id, p.bloodline_potential, p.bloodline_talent),
                         ("byakugan", 27, 54))
        self.assertFalse(kkg.ensure_hyuga_inheritance(p))
        self.assertEqual(p.bloodline_potential, 27)

    def test_weak_potential_can_master_core_arts_but_not_celestial(self):
        p = hyuga_player(40, 40)
        self.assertTrue(hyuga.unlocked(p, "eight trigrams sixty-four palms"))
        self.assertFalse(hyuga.unlocked(p, "celestial byakugan"))
        self.assertFalse(hyuga.unlocked(p, "tenseigan chakra mode"))
        self.assertFalse(hyuga.unlocked(p, "golden wheel reincarnation explosion"))

    def test_tenseigan_requires_absolute_maximum_potential_and_mastery(self):
        for potential, mastery in [(99, 99), (100, 99), (99, 100)]:
            p = hyuga_player(potential, mastery)
            self.assertFalse(hyuga.unlocked(p, "tenseigan chakra mode"))
        ultimate = hyuga_player(100, 100)
        self.assertTrue(hyuga.unlocked(ultimate, "tenseigan chakra mode"))
        self.assertTrue(hyuga.unlocked(ultimate, "golden wheel reincarnation explosion"))
        ultimate.level = 239
        self.assertFalse(hyuga.unlocked(ultimate, "tenseigan chakra mode"))
        ultimate.level = 240
        self.assertTrue(hyuga.unlocked(ultimate, "tenseigan chakra mode"))

    def test_technique_progression_spans_full_250_levels(self):
        self.assertEqual(hyuga.REGISTRY["byakugan"]["level_requirement"], 25)
        self.assertEqual(hyuga.REGISTRY["gentle fist: chakra point strike"]["level_requirement"], 35)
        self.assertEqual(hyuga.REGISTRY["celestial byakugan"]["level_requirement"], 215)
        self.assertEqual(hyuga.REGISTRY["tenseigan chakra mode"]["level_requirement"], 240)
        self.assertEqual(hyuga.REGISTRY["golden wheel reincarnation explosion"]["level_requirement"], 250)
        elite = hyuga_player(potential=100, mastery=100, level=249)
        self.assertFalse(hyuga.unlocked(elite, "golden wheel reincarnation explosion"))
        elite.level = 250
        self.assertTrue(hyuga.unlocked(elite, "golden wheel reincarnation explosion"))

    def test_byakugan_activation_needs_awakening_not_teacher(self):
        p = hyuga_player(25, 0, level=25)
        class Session:
            player = p
            messages = []
            def send(self, message):
                self.messages.append(message)
        s = Session()
        self.assertIn("byakugan", commands.COMMANDS)
        hyuga.cmd_byakugan(s, [])
        self.assertTrue(p.byakugan_active)
        hyuga.cmd_byakugan(s, ["off"])
        self.assertFalse(p.byakugan_active)

    def test_top_secret_celestial_help_requires_personal_unlock(self):
        from types import SimpleNamespace as NS
        import mangekyo_discovery
        p = hyuga_player(potential=100, mastery=100, level=200)
        session = NS(player=p, account=NS(staff_level="player"))
        page = {"primary_keyword": "tenseigan chakra mode"}
        self.assertFalse(mangekyo_discovery.can_read(session, page))
        p.level = 240
        self.assertTrue(mangekyo_discovery.can_read(session, page))
        p.bloodline_potential = 75
        self.assertFalse(mangekyo_discovery.can_read(session, page))
        session.account.staff_level = "administrator"
        self.assertTrue(mangekyo_discovery.can_read(session, page))

    def test_registry_shortcuts_and_guard_definitions(self):
        import status_effects
        import jutsu_shortcuts
        self.assertEqual(set(hyuga.REGISTRY) - set(data_jutsu.JUTSU), set())
        self.assertEqual(set(jutsu_shortcuts.JUTSU_SHORTCUTS) - set(data_jutsu.JUTSU), set())
        self.assertIn("hyuga_rotation", status_effects.EFFECT_DEFS)
        self.assertEqual(data_jutsu.JUTSU["gentle step twin lion fists"]["kkg_gate"], "byakugan")


if __name__ == "__main__":
    unittest.main()
