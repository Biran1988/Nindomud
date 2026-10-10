"""Ice Release unlocks and combat gates follow the revealed nature pair."""

import unittest
from unittest.mock import patch

import combat
import data_jutsu
import data_kekkei_genkai as kkg
import help_system
import leveling
from models import Player
from session import Session, State


class IceReleaseTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Haku", "Haku", primary_class="taijutsu", level=75)
        self.player.chakra_nature = "water"
        self.player.chakra_nature_revealed = True
        self.player.chakra_nature_secondary = "wind"
        self.player.chakra_nature_secondary_revealed = True

    def test_unlocks_by_release_and_level_across_classes(self):
        self.assertEqual(data_jutsu.match_prefix(["demonic", "bandit"]),
                         ("demonic illusion hell viewing technique", 1))
        self.assertEqual(data_jutsu.match_prefix(["demonic", "mirroring", "ice", "crystals", "bandit"]),
                         ("demonic mirroring ice crystals", 4))
        self.assertTrue(kkg.sync_elemental_release(self.player))
        self.assertEqual(self.player.elemental_release_id, "ice_release")
        for key in ("ice senbon", "ice prison", "demonic mirroring ice crystals"):
            jutsu = data_jutsu.JUTSU[key]
            self.assertIn(jutsu["display_name"], self.player.learned_skills)
            self.assertTrue(combat._can_use_jutsu(self.player, jutsu, key))
            self.assertNotIn(key, data_jutsu.all_unlocked_for_class("ninjutsu", 100))

        self.player.level = 30
        kkg.sync_elemental_techniques(self.player)
        self.assertIn("Ice Senbon", self.player.learned_skills)
        self.assertNotIn("Ice Prison", self.player.learned_skills)
        self.assertFalse(combat._can_use_jutsu(self.player, data_jutsu.JUTSU["ice prison"], "ice prison"))
        self.player.level = 24
        kkg.sync_elemental_techniques(self.player)
        self.assertNotIn("Ice Senbon", self.player.learned_skills)
        self.assertFalse(combat._can_use_jutsu(self.player, data_jutsu.JUTSU["ice senbon"], "ice senbon"))

    def test_revoke_on_clan_bloodline_or_nature_change(self):
        kkg.sync_elemental_release(self.player)
        self.player.bloodline_id = "sharingan"
        self.assertTrue(kkg.sync_elemental_release(self.player))
        self.assertIsNone(self.player.elemental_release_id)
        self.assertNotIn("Ice Senbon", self.player.learned_skills)
        self.assertFalse(combat._can_use_jutsu(self.player, data_jutsu.JUTSU["ice senbon"], "ice senbon"))
        self.player.bloodline_id = None
        self.player.chakra_nature_secondary = "earth"
        kkg.sync_elemental_release(self.player)
        self.assertEqual(self.player.elemental_release_id, "wood_release")
        self.assertNotIn("Ice Senbon", self.player.learned_skills)

    def test_returning_character_and_help(self):
        self.player.elemental_release_id = "ice_release"
        with patch.object(leveling.storage, "save_player") as save:
            messages = leveling.sync_universal_skills(self.player)
        self.assertTrue(any("Ice Prison" in message for message in messages))
        save.assert_called_once()
        for key in ("ice senbon", "ice prison", "demonic mirroring ice crystals"):
            page = next(entry for entry in help_system.DEFAULT_HELP_ENTRIES
                        if entry["primary_keyword"] == key)
            self.assertIn("Requires Ice Release", page["body"])

    def test_ice_prison_hits_and_applies_control(self):
        kkg.sync_elemental_release(self.player)
        self.player.chakra = 500
        self.player.room_vnum = 991199
        messages = []
        session = Session(messages.append, lambda: None)
        session.state = State.PLAYING
        session.player = self.player
        mob = combat.Mob(991199, 991199, "Bandit", 40, 500, 500,
                         991199, 0, 0)
        try:
            with patch.object(combat.random, "randint", return_value=1):
                combat.use_jutsu(session, "ice prison", mob)
            self.assertLess(mob.health, 500)
            self.assertIn("paralyzed", mob.active_status_effects)
            self.assertLess(self.player.chakra, 500)
        finally:
            from session import ACTIVE_SESSIONS
            ACTIVE_SESSIONS.remove(session)


if __name__ == "__main__":
    unittest.main()
