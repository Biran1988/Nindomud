"""Authenticated immortals receive and can test the complete jutsu roster."""

import unittest
from unittest.mock import patch

import combat
import data_jutsu
import element_choice
import leveling
from models import Account, Player
from session import ACTIVE_SESSIONS, Session, State


class ImmortalJutsuTests(unittest.TestCase):
    def test_all_jutsu_granted_and_staff_gates_bypassed(self):
        player = Player("Tester", "Tester", level=1, primary_class="taijutsu")
        player.practice_gate_enabled = True
        player._immortal_skill_mastery = True
        self.assertTrue(leveling.grant_immortal_jutsu(player))
        self.assertTrue(all(j["display_name"] in player.learned_skills
                            and player.skill_proficiencies[j["display_name"]] == 100
                            for j in data_jutsu.JUTSU.values()))
        self.assertIn("1000 Years of Death", player.learned_skills)  # scroll-only

        session = Session(lambda text: None, lambda: None)
        session.account = Account("Tester", "salt", "hash", staff_level="helper")
        session.player = player
        session.state = State.PLAYING
        try:
            self.assertTrue(all(combat._can_use_jutsu(player, j, key)
                                for key, j in data_jutsu.JUTSU.items()))
            player.chakra = 500
            player.room_vnum = 991199
            mob = combat.Mob(991199, 991199, "Bandit", 40, 500, 500, 991199, 0, 0)
            with patch.object(combat.random, "randint", return_value=1):
                combat.use_jutsu(session, "ice prison", mob)
            self.assertLess(mob.health, 500)
            self.assertFalse(element_choice.begin(session))
            self.assertFalse(element_choice.handle_command(session, "perform ice prison mob"))
            session.account.staff_level = "player"
            self.assertFalse(combat._can_use_jutsu(player, data_jutsu.JUTSU["ice prison"], "ice prison"))
            self.assertFalse(combat._can_use_jutsu(player, data_jutsu.JUTSU["atomic dissolution"], "atomic dissolution"))
        finally:
            ACTIVE_SESSIONS.remove(session)

    def test_regular_player_does_not_receive_staff_jutsu(self):
        player = Player("Genin", "Genin", level=1)
        self.assertFalse(leveling.grant_immortal_jutsu(player))
        self.assertNotIn("Ice Prison", player.learned_skills)


if __name__ == "__main__":
    unittest.main()
