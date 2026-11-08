"""Elemental KKGK Taijutsu parity and live combat regression tests."""
import unittest
from unittest.mock import patch

import combat
import data_handsigns
import data_jutsu
import data_kekkei_genkai as kkg
import elemental_release_arts
import help_system
import taijutsu_elemental_release_arts as physical_arts
from models import Player
from session import Session, State, ACTIVE_SESSIONS


def physical_player(release, level=75, primary_class="taijutsu"):
    pairs = {value: pair for pair, value in kkg.ELEMENTAL_RELEASES.items()}
    natures = sorted(pairs[release]) if release != "dust_release" else ["earth", "wind", "fire"]
    p = Player("Striker", "Striker", primary_class=primary_class, level=level)
    p.chakra_nature = natures[0]
    p.chakra_nature_revealed = True
    p.chakra_nature_secondary = natures[1]
    p.chakra_nature_secondary_revealed = True
    if len(natures) > 2:
        p.chakra_nature_tertiary = natures[2]
        p.chakra_nature_tertiary_revealed = True
    p.chakra = p.stamina = 10000
    return p


class TaijutsuElementalKKGKTests(unittest.TestCase):
    def test_full_roster_matches_ninjutsu_releases(self):
        moves = {k: v for k, v in data_jutsu.JUTSU.items()
                 if v.get("jutsu_type") == "kkgk_taijutsu_strike"}
        self.assertEqual(len(moves), 33)
        self.assertEqual({x["kkg_gate"] for x in moves.values()},
                         set(kkg.ELEMENTAL_RELEASE_NAMES))
        for release, physical in physical_arts.TAIJUTSU_MOVES.items():
            expected = (elemental_release_arts.DUST_TIERS if release == "dust_release"
                        else elemental_release_arts.ICE_TIERS)
            self.assertEqual(len(physical), 3)
            entries = [v for v in moves.values() if v["kkg_gate"] == release]
            self.assertEqual(sorted(v["level_requirement"] for v in entries),
                             sorted(tier[0] for tier in expected))
            for v in entries:
                self.assertEqual(v["class_requirement"], "taijutsu")
                self.assertEqual(v["damage_type"], "physical")
                self.assertTrue(v["melee_only"])
                self.assertGreater(v["stamina_cost"], v["chakra_cost"])
                self.assertFalse(data_handsigns.has_handsigns(v))

    def test_all_releases_auto_unlock_only_for_taijutsu(self):
        for release in kkg.ELEMENTAL_RELEASE_NAMES:
            level = 100 if release == "dust_release" else 75
            with self.subTest(release=release):
                p = physical_player(release, level)
                self.assertTrue(kkg.sync_elemental_release(p))
                physical = [v for v in data_jutsu.JUTSU.values()
                            if v.get("jutsu_type") == "kkgk_taijutsu_strike"
                            and v["kkg_gate"] == release]
                self.assertEqual(len(physical), 3)
                for v in physical:
                    self.assertIn(v["display_name"], p.learned_skills)
                    self.assertTrue(combat._can_use_jutsu(p, v, v["display_name"].lower()))
                other = physical_player(release, level, "ninjutsu")
                kkg.sync_elemental_release(other)
                for v in physical:
                    self.assertNotIn(v["display_name"], other.learned_skills)
                    self.assertFalse(combat._can_use_jutsu(other, v, v["display_name"].lower()))

    def test_level_prerequisites_and_revocation(self):
        p = physical_player("ice_release", level=30)
        kkg.sync_elemental_release(p)
        self.assertIn("Frost Knuckle", p.learned_skills)
        self.assertNotIn("Glacier Heel", p.learned_skills)
        p.level = 45
        kkg.sync_elemental_techniques(p)
        self.assertIn("Glacier Heel", p.learned_skills)
        p.level = 70
        kkg.sync_elemental_techniques(p)
        self.assertIn("Mirrored Lotus Rush", p.learned_skills)
        p.bloodline_id = "sharingan"
        kkg.sync_elemental_release(p)
        self.assertNotIn("Frost Knuckle", p.learned_skills)
        self.assertFalse(combat._can_use_jutsu(
            p, data_jutsu.JUTSU["frost knuckle"], "frost knuckle"))

    def test_unchanged_ninjutsu_roster_and_kkgk_help(self):
        self.assertIn("Ice Senbon", [x["display_name"] for x in data_jutsu.JUTSU.values()])
        pages = {x["primary_keyword"]: x for x in help_system.DEFAULT_HELP_ENTRIES}
        self.assertIn("elemental taijutsu", pages)
        for release, entries in physical_arts.TAIJUTSU_MOVES.items():
            for name, _flavor in entries:
                key = name.lower()
                self.assertIn(key, pages)
                self.assertIn("physical", pages[key]["body"].lower())
                self.assertIn("no hand signs", pages[key]["body"].lower())

    def test_physical_hit_pays_stamina_and_applies_effect(self):
        player = physical_player("ice_release", level=75)
        kkg.sync_elemental_release(player)
        player.room_vnum = 991199
        session = Session(lambda line: None, lambda: None)
        session.state = State.PLAYING
        session.player = player
        mob = combat.Mob(991199, 991199, "Bandit", 75, 500000, 500000,
                         991199, 0, 0)
        starting_chakra = player.chakra
        starting_stamina = player.stamina
        try:
            with patch.object(combat.random, "randint", return_value=1):
                combat.use_jutsu(session, "frost knuckle", mob)
            self.assertLess(mob.health, 500000)
            self.assertIn("off_balance", mob.active_status_effects)
            self.assertLess(player.stamina, starting_stamina)
            self.assertLess(player.chakra, starting_chakra)
        finally:
            if session in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS.remove(session)


if __name__ == "__main__":
    unittest.main()
