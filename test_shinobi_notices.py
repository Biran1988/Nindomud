"""Regression tests for shinobi-themed connection and leveling notices."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ascii_art
import commands
import jobs
import leveling
import session
import shinobi_notices
from models import Player


class ShinobiNoticesTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Tester", "Tester")
        self.player.village = "leaf"
        self.player.clan = "nara"
        self.player.primary_class = "ninjutsu"
        self.viewer = Player("Spectator", "Spectator")
        self.owner_session = SimpleNamespace(
            state=session.State.PLAYING, player=self.player, send=Mock(),
            request_close=Mock()
        )
        self.viewer_session = SimpleNamespace(
            state=session.State.PLAYING, player=self.viewer, send=Mock()
        )
        self.patcher = patch.object(
            session, "ACTIVE_SESSIONS", [self.owner_session, self.viewer_session]
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_login_and_logout_design(self):
        splash = ascii_art.login_screen()
        self.assertIn("FORGE YOUR OWN LEGEND", splash)
        self.assertIn("THE FIVE GREAT SHINOBI VILLAGES", splash)
        self.assertIn("SHINOBI ARRIVAL", shinobi_notices.arrival(self.player.name))
        self.assertIn("SHINOBI DEPARTURE", shinobi_notices.departure(self.player.name))
        self.assertIn("WELCOME TO YOUR NINJA WAY", shinobi_notices.welcome(
            self.player, "Hidden Leaf Village"
        ))

    def test_quit_uses_themed_farewell_and_saves(self):
        with patch.object(commands.storage, "save_player") as save:
            commands.cmd_quit(self.owner_session, [])
        save.assert_called_once_with(self.player)
        self.owner_session.request_close.assert_called_once_with()
        self.assertIn("UNTIL NEXT TIME", self.owner_session.send.call_args.args[0])

    def test_combat_level_broadcasts_once_to_other_online_players(self):
        self.player.experience = leveling.xp_for_next_level(1) - 1
        with patch.object(leveling.storage, "save_player"):
            personal = leveling.grant_experience(self.player, 1)
        self.assertEqual(self.player.level, 2)
        self.assertTrue(any("reached level 2" in line for line in personal))
        notices = [call.args[0] for call in self.viewer_session.send.call_args_list]
        self.assertEqual(len(notices), 1)
        self.assertIn("SHINOBI LEVEL UP", notices[0])
        self.assertIn("Ninja Level 2", notices[0])
        self.owner_session.send.assert_not_called()

    def test_job_level_broadcasts_without_ninja_level_change(self):
        personal = jobs.add_job_xp(self.player, "mining", jobs.job_xp_for_level(2))
        self.assertEqual(self.player.level, 1)
        self.assertEqual(jobs.get_job_level(self.player, "mining"), 2)
        self.assertTrue(any("Mining level increased" in line for line in personal))
        notice = self.viewer_session.send.call_args.args[0]
        self.assertIn("JOB LEVEL UP", notice)
        self.assertIn("Mining Level 2", notice)
        self.owner_session.send.assert_not_called()

    def test_multiple_job_levels_announce_each_earned_level(self):
        jobs.add_job_xp(self.player, "fishing", jobs.job_xp_for_level(3))
        sent = [call.args[0] for call in self.viewer_session.send.call_args_list]
        self.assertEqual(len(sent), 2)
        self.assertIn("Fishing Level 2", sent[0])
        self.assertIn("Fishing Level 3", sent[1])

    def test_offline_progress_does_not_announce(self):
        session.ACTIVE_SESSIONS.remove(self.owner_session)
        jobs.add_job_xp(self.player, "farming", jobs.job_xp_for_level(2))
        self.viewer_session.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
