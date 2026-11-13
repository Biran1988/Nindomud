"""Immortal-appointed Descendant of the Six Paths does not alter birth rolls."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import reincarnation
import six_paths
import six_paths_staff
from models import Player


class SixPathsDescendantTests(unittest.TestCase):
    def setUp(self):
        self.owner = NS(
            account=NS(name="biran", staff_level="implementor"),
            player=Player("Biran", "biran"),
            send=Mock(), send_prompt=Mock(),
        )
        self.target = Player(
            "Target", "Target", level=75, primary_class="taijutsu",
            reincarnation="indra", reincarnation_birth_clan="uchiha",
            chakra=1000, maximum_chakra=1000,
        )
        self.live = NS(player=self.target, send=Mock(), send_prompt=Mock())

    def invoke(self, action):
        with (patch("olc._find_target_player", return_value=(self.target, self.live)),
              patch("storage.save_player") as saved):
            six_paths_staff.command(self.owner, ["Target", action])
            return saved.call_count

    def test_grant_overrides_six_paths_branch_but_not_birth_reincarnation(self):
        self.assertEqual(self.invoke("ashura"), 1)
        self.assertEqual(self.target.six_paths_descendant, "ashura")
        self.assertEqual(self.target.reincarnation, "indra")
        self.assertEqual(self.target.reincarnation_birth_clan, "uchiha")
        self.assertEqual(six_paths._soul(self.target), "ashura")
        self.assertTrue(six_paths.eligible(self.target, "ashura"))
        self.assertFalse(six_paths.eligible(self.target, "indra"))
        for skill in (six_paths.MODE_SKILLS["ashura"], *six_paths.TECHNIQUES["ashura"]):
            self.assertIn(skill, self.target.learned_skills)
        self.assertEqual(self.target.maximum_chakra, 1000)
        self.assertEqual(Player.from_dict(self.target.to_dict()).six_paths_descendant, "ashura")
        self.assertFalse(Player.from_dict({k: v for k, v in self.target.to_dict().items()
                                           if k != "six_paths_descendant"}).six_paths_descendant)

    def test_revocation_restores_natural_lineage_and_disables_active_mode(self):
        self.invoke("ashura")
        self.target.six_paths_active = True
        self.assertEqual(self.invoke("off"), 1)
        self.assertFalse(self.target.six_paths_descendant)
        self.assertFalse(self.target.six_paths_active)
        self.assertEqual(six_paths._soul(self.target), "indra")
        self.assertTrue(six_paths.eligible(self.target, "indra"))
        self.assertFalse(six_paths.eligible(self.target, "ashura"))

    def test_level_gate_and_later_awaken(self):
        self.target.reincarnation = ""
        self.target.level = 74
        self.assertEqual(self.invoke("indra"), 1)
        self.assertFalse(six_paths.eligible(self.target))
        self.assertNotIn("Six Paths Rinnegan", self.target.learned_skills)
        self.target.level = 75
        six_paths.sync_skills(self.target)
        self.assertTrue(six_paths.eligible(self.target))
        self.assertIn("Six Paths Rinnegan", self.target.learned_skills)

    def test_staff_permissions_and_invalid_branch(self):
        self.owner.account.staff_level = "player"
        self.assertEqual(self.invoke("indra"), 0)
        self.assertFalse(self.target.six_paths_descendant)
        self.owner.account.staff_level = "helper"
        self.assertEqual(self.invoke("neither"), 0)
        self.assertEqual(self.invoke("indra"), 1)
        self.assertEqual(self.target.six_paths_descendant, "indra")

    def test_command_aliases_and_readable_ancestry(self):
        self.assertIs(commands.COMMANDS["sixdescendant"], six_paths_staff.command)
        self.assertIs(commands.COMMANDS["sixpathsset"], six_paths_staff.command)
        self.invoke("ashura")
        self.assertTrue(any("Ashura" in args.args[0]
                            for args in self.live.send.call_args_list))
        message = NS(player=self.target, send=Mock())
        reincarnation.command(message, [])
        self.assertIn("Descendant of the Six Paths", message.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
