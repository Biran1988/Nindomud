"""NPC jutsu combat: class and level gates, resources and real damage."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import data_jutsu
import mob_jutsu
from models import Player


class MobJutsuTests(unittest.TestCase):
    def make_mob(self, level=25, role="ninjutsu"):
        return combat.Mob(
            99771, 99771, "Test Shinobi", level, 1000, 1000,
            99772, 0, 0, chakra=300, maximum_chakra=300,
            stamina=300, maximum_stamina=300, primary_class=role,
            chakra_nature="fire",
        )

    def make_session(self, hp=500):
        player = Player("Target", "Target", village="leaf", room_vnum=99772,
                        health=hp, maximum_health=hp)
        return NS(player=player, account=NS(staff_level="player"),
                  send=Mock(), combat_target=None)

    def test_level_one_through_nine_never_use_jutsu(self):
        for level in (1, 5, 9):
            mob = self.make_mob(level)
            session = self.make_session()
            self.assertEqual(mob_jutsu.available_jutsu(mob), [])
            with patch("mob_jutsu.random.randint") as rng:
                self.assertFalse(mob_jutsu.try_cast(session, mob))
                rng.assert_not_called()
            self.assertEqual(session.player.health, 500)
            self.assertEqual(mob.chakra, 300)

    def test_level_ten_and_all_four_classes_have_appropriate_attacks(self):
        expected = {
            "ninjutsu": "Chakra Ball",
            "taijutsu": "Choku Zuki",
            "genjutsu": "Distortion Flame",
            "bukijutsu": "Throw Shuriken",
        }
        for role, jutsu in expected.items():
            mob = self.make_mob(10, role)
            abilities = [art["display_name"] for _, art in mob_jutsu.available_jutsu(mob)]
            self.assertIn(jutsu, abilities, role)
            self.assertTrue(all(art["level_requirement"] <= 10
                                for _, art in mob_jutsu.available_jutsu(mob)))
        no_class = self.make_mob(50, None)
        self.assertEqual(mob_jutsu.available_jutsu(no_class), [])

    def test_level_and_element_and_special_art_restrictions(self):
        mob = self.make_mob(75, "ninjutsu")
        available = dict(mob_jutsu.available_jutsu(mob))
        self.assertIn("karyuu endan", available)
        self.assertNotIn("suigadan", available)  # water nature required
        self.assertNotIn("kamui limb removal", available)
        self.assertNotIn("1000 years of death", available)
        self.assertNotIn("shadow clone jutsu", available)
        mob.chakra = 0
        self.assertFalse(any(art.get("chakra_cost", 0) > 0
                             for _, art in mob_jutsu.available_jutsu(mob)))

    def test_spell_costs_chakra_and_replaces_melee_with_real_damage(self):
        mob = self.make_mob(25)
        session = self.make_session()
        art = data_jutsu.JUTSU["chakra ball"]
        with patch("mob_jutsu.available_jutsu", return_value=[("chakra ball", art)]), \
             patch("mob_jutsu.time.time", return_value=100.0), \
             patch("mob_jutsu.random.randint", return_value=1), \
             patch("mob_jutsu.random.choice", side_effect=lambda seq: seq[0]), \
             patch("combat.roll_jutsu_damage", return_value=(40, False)):
            self.assertTrue(mob_jutsu.try_cast(session, mob))
            self.assertEqual(session.player.health, 460)
            self.assertEqual(mob.chakra, 300 - art["chakra_cost"])
            self.assertEqual(mob.next_jutsu_at, 108.0)
            self.assertEqual(mob.jutsu_cooldowns["chakra ball"], 100 + art["cooldown"])
            self.assertFalse(mob_jutsu.try_cast(session, mob))
            self.assertEqual(session.player.health, 460)
        self.assertTrue(any("Chakra Ball" in call.args[0]
                            for call in session.send.call_args_list))

    def test_kamui_defends_against_a_mob_jutsu(self):
        mob = self.make_mob(25)
        session = self.make_session()
        session.player.kamui_intangibility_rounds_left = 2
        art = data_jutsu.JUTSU["chakra ball"]
        with patch("mob_jutsu.available_jutsu", return_value=[("chakra ball", art)]), \
             patch("mob_jutsu.time.time", return_value=100.0), \
             patch("mob_jutsu.random.randint", return_value=1), \
             patch("mob_jutsu.random.choice", side_effect=lambda seq: seq[0]):
            self.assertTrue(mob_jutsu.try_cast(session, mob))
        self.assertEqual(session.player.health, 500)
        self.assertEqual(session.player.kamui_intangibility_rounds_left, 1)
        self.assertEqual(mob.chakra, 300 - art["chakra_cost"])

    def test_critical_defeat_uses_existing_hospital_handler(self):
        mob = self.make_mob(50)
        session = self.make_session(hp=5)
        art = data_jutsu.JUTSU["chakra ball"]
        with patch("mob_jutsu.available_jutsu", return_value=[("chakra ball", art)]), \
             patch("mob_jutsu.time.time", return_value=100.0), \
             patch("mob_jutsu.random.randint", return_value=1), \
             patch("mob_jutsu.random.choice", side_effect=lambda seq: seq[0]), \
             patch("combat.roll_jutsu_damage", return_value=(40, False)), \
             patch("combat.handle_player_defeat") as defeat:
            self.assertTrue(mob_jutsu.try_cast(session, mob))
        defeat.assert_called_once_with(session)

    def test_between_fights_chakra_regeneration(self):
        mob = self.make_mob(20)
        mob.chakra = 1
        mob.stamina = 1
        with patch.dict(combat.MOBS_BY_ROOM, {99772: [mob]}, clear=True), \
             patch("combat._mob_is_being_fought", return_value=False):
            combat.tick_all_mob_effects()
        self.assertGreater(mob.chakra, 1)
        self.assertGreater(mob.stamina, 1)


if __name__ == "__main__":
    unittest.main()
