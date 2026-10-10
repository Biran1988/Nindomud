"""Every elemental release has gated, balanced techniques and help."""

import unittest

import combat
import data_handsigns
import data_jutsu
import data_kekkei_genkai as kkg
import help_system
import status_effects
from models import Player


class ElementalReleaseArtsTests(unittest.TestCase):
    def techniques(self, release_id):
        return [(key, jutsu) for key, jutsu in data_jutsu.JUTSU.items()
                if jutsu.get("kkg_gate") == release_id]

    def test_every_pair_grants_three_moves_at_or_after_second_reveal(self):
        for pair, release_id in kkg.ELEMENTAL_RELEASES.items():
            with self.subTest(release=release_id):
                moves = self.techniques(release_id)
                self.assertEqual([j["level_requirement"] for _key, j in moves], [25, 45, 70])
                player = Player("Tester", "Tester", primary_class="taijutsu", level=24)
                player.chakra_nature, player.chakra_nature_secondary = sorted(pair)
                player.chakra_nature_revealed = True
                player.chakra_nature_secondary_revealed = True
                kkg.sync_elemental_release(player)
                self.assertTrue(all(not combat._can_use_jutsu(player, j, key) for key, j in moves))
                for level, unlocked in ((25, 1), (44, 1), (45, 2), (69, 2), (70, 3)):
                    player.level = level
                    kkg.sync_elemental_techniques(player)
                    self.assertEqual(sum(j["display_name"] in player.learned_skills for _key, j in moves), unlocked)
                    self.assertEqual(sum(combat._can_use_jutsu(player, j, key) for key, j in moves), unlocked)
                player.chakra_nature_secondary_revealed = False
                kkg.sync_elemental_release(player)
                self.assertTrue(all(not combat._can_use_jutsu(player, j, key) for key, j in moves))

    def test_dust_unlocks_only_after_third_nature(self):
        moves = self.techniques("dust_release")
        self.assertEqual(len(moves), 3)
        player = Player("Dust", "Dust", level=100)
        player.chakra_nature = "earth"
        player.chakra_nature_secondary = "wind"
        player.chakra_nature_revealed = player.chakra_nature_secondary_revealed = True
        kkg.sync_elemental_release(player)
        self.assertTrue(all(not combat._can_use_jutsu(player, j, key) for key, j in moves))
        player.chakra_nature_tertiary = "fire"
        player.chakra_nature_tertiary_revealed = True
        kkg.sync_elemental_release(player)
        self.assertEqual(player.elemental_release_id, "dust_release")
        self.assertTrue(all(combat._can_use_jutsu(player, j, key) for key, j in moves))

    def test_balance_handsigns_statuses_and_individual_help(self):
        self.assertEqual(len(kkg.ELEMENTAL_RELEASE_NAMES), 11)
        ice = self.techniques("ice_release")
        for release_id in kkg.ELEMENTAL_RELEASE_NAMES:
            moves = self.techniques(release_id)
            self.assertEqual(len(moves), 3)
            release_page = next(e for e in help_system.DEFAULT_HELP_ENTRIES
                                if e["primary_keyword"] == kkg.ELEMENTAL_RELEASE_NAMES[release_id].lower())
            for index, (key, jutsu) in enumerate(moves):
                with self.subTest(move=key):
                    self.assertIn(jutsu["display_name"], release_page["body"])
                    self.assertIn(jutsu["effect"], status_effects.EFFECT_DEFS)
                    self.assertGreaterEqual(jutsu["level_requirement"], kkg.ELEMENTAL_RELEASE_REVEAL_LEVEL)
                    self.assertGreaterEqual(len(data_handsigns.sequence_for(key)), 2)
                    page = next(e for e in help_system.DEFAULT_HELP_ENTRIES if e["primary_keyword"] == key)
                    self.assertIn(kkg.ELEMENTAL_RELEASE_NAMES[release_id], page["body"])
                    self.assertIn(f"{jutsu['damage'][0]}-{jutsu['damage'][1]}", page["body"])
                    if release_id != "dust_release":
                        ice_jutsu = ice[index][1]
                        self.assertEqual(jutsu["damage"], ice_jutsu["damage"])
                        self.assertEqual(jutsu["chakra_cost"], ice_jutsu["chakra_cost"])
                        self.assertEqual(jutsu["cooldown"], ice_jutsu["cooldown"])


if __name__ == "__main__":
    unittest.main()
