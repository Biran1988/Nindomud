"""Staff Six Paths descendant appointment and persistence tests."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import six_paths
import commands
from models import Player


class DescendantAppointmentTests(unittest.TestCase):
    def setUp(self):
        self.target = Player("Shinobi", "Shinobi", level=75,
                             reincarnation="", six_paths_descendant="",
                             health=100, chakra=100, stamina=100)
        self.target_session = NS(player=self.target, send=Mock(), send_prompt=Mock())
        self.admin = NS(account=NS(staff_level="administrator"),
                        send=Mock())

    def test_online_grant_and_withdraw_without_changing_birth(self):
        with patch("olc._find_target_player", return_value=(self.target, self.target_session)), \
             patch("storage.save_player") as save:
            commands.COMMANDS["sixdesc"](self.admin, ["Shinobi", "indra"])
            self.assertEqual(self.target.six_paths_descendant, "indra")
            self.assertEqual(self.target.reincarnation, "")
            self.assertTrue(six_paths.eligible(self.target, "indra"))
            self.assertFalse(six_paths.eligible(self.target, "ashura"))
            self.assertIn("Six Paths Rinnegan", self.target.learned_skills)
            save.assert_called_with(self.target)
            self.target.six_paths_active = True
            commands.COMMANDS["descendant"](self.admin, ["Shinobi", "none"])
            self.assertFalse(self.target.six_paths_active)
            self.assertEqual(self.target.six_paths_descendant, "")
            self.assertFalse(six_paths.eligible(self.target))

    def test_offline_grant_keeps_level_gate(self):
        self.target.level = 74
        with patch("olc._find_target_player", return_value=(self.target, None)), \
             patch("storage.save_player") as save:
            six_paths.appoint_descendant(self.admin, ["Shinobi", "ashura"])
        self.assertFalse(six_paths.eligible(self.target))
        self.assertNotIn("Six Paths Sage Mode", self.target.learned_skills)
        self.target.level = 75
        self.assertEqual(len(six_paths.sync_skills(self.target)), 3)
        self.assertTrue(six_paths.eligible(self.target, "ashura"))
        save.assert_called_once_with(self.target)

    def test_non_admin_rejected_and_bad_target_never_saved(self):
        self.admin.account.staff_level = "helper"
        with patch("olc._find_target_player") as lookup, \
             patch("storage.save_player") as save:
            six_paths.appoint_descendant(self.admin, ["Shinobi", "indra"])
        lookup.assert_not_called()
        save.assert_not_called()
        self.admin.account.staff_level = "administrator"
        with patch("olc._find_target_player") as lookup, \
             patch("storage.save_player") as save:
            six_paths.appoint_descendant(self.admin, ["../Shinobi", "indra"])
        lookup.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
