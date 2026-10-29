"""Staff bulk proficiency command: live/offline, filtering and permissions."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import immortal_practice
from models import Player


class MassPracticeTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(account=NS(staff_level="implementor"), send=Mock(),
                        send_paginated=Mock())
        self.offline = Player("Offline", "Offline")
        self.offline.learned_skills = ["Shadow Clone Jutsu", "Strong Fist"]
        self.offline.skill_proficiencies = {"Shadow Clone Jutsu": 4, "Strong Fist": 55}
        self.online = Player("Online", "Online")
        self.online.learned_skills = ["Shadow Clone Jutsu"]
        self.online.skill_proficiencies = {"Shadow Clone Jutsu": 20}
        self.unskilled = Player("Other", "Other")
        self.unskilled.learned_skills = ["Dynamic Entry"]
        self.unskilled.skill_proficiencies = {"Dynamic Entry": 10}
        self.live = NS(player=self.online, state=NS(name="PLAYING"))
        self.disk_snapshot = Player.from_dict(self.online.to_dict())
        self.disk_snapshot.skill_proficiencies["Shadow Clone Jutsu"] = 2
        self.saved = []
        patcher = patch("immortal_practice.storage.all_players",
                        return_value=[self.offline, self.disk_snapshot, self.unskilled])
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("session.ACTIVE_SESSIONS", [self.live])
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("immortal_practice.storage.save_player",
                        side_effect=lambda p: self.saved.append(
                            (p.name, dict(p.skill_proficiencies))))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_registered_command_sets_all_known_online_and_offline(self):
        self.assertIs(commands.COMMANDS["setallprac"], immortal_practice.command)
        immortal_practice.command(self.actor, ["shadow", "clone", "jutsu", "75"])
        self.assertEqual(self.offline.skill_proficiencies["Shadow Clone Jutsu"], 75)
        self.assertEqual(self.online.skill_proficiencies["Shadow Clone Jutsu"], 75)
        self.assertEqual(self.disk_snapshot.skill_proficiencies["Shadow Clone Jutsu"], 2)
        self.assertEqual(self.unskilled.skill_proficiencies, {"Dynamic Entry": 10})
        self.assertEqual({name for name, _ in self.saved}, {"Offline", "Online"})
        self.assertIn("Shadow Clone Jutsu", self.offline.practiced_skills)
        self.assertIn("Shadow Clone Jutsu", self.online.practiced_skills)
        self.assertIn("2 existing character(s)", self.actor.send.call_args.args[0])

    def test_who_view_lists_proficiency_without_modifying(self):
        immortal_practice.command(self.actor, ["who", "SHADOW", "CLONE", "JUTSU"])
        result = self.actor.send_paginated.call_args.args[0]
        self.assertIsInstance(result, str)
        self.assertIn("Offline", result)
        self.assertIn("Online", result)
        self.assertIn("4%", result)
        self.assertIn("20%", result)
        self.assertNotIn("2%", result)
        self.assertEqual(self.saved, [])

    def test_existing_non_jutsu_skill_works_and_unlearned_not_granted(self):
        immortal_practice.command(self.actor, ["strong", "fist", "1"])
        self.assertEqual(self.offline.skill_proficiencies["Strong Fist"], 1)
        self.assertNotIn("Strong Fist", self.online.learned_skills)
        self.assertNotIn("Strong Fist", self.online.skill_proficiencies)
        self.assertEqual([name for name, _ in self.saved], ["Offline"])

    def test_normal_players_and_invalid_percent_cannot_edit(self):
        self.actor.account.staff_level = "player"
        immortal_practice.command(self.actor, ["dynamic", "entry", "100"])
        self.assertIn("Only Administrators", self.actor.send.call_args.args[0])
        self.actor.account.staff_level = "administrator"
        for amount in ("0", "101", "twenty", "12.5"):
            immortal_practice.command(self.actor, ["shadow", "clone", amount])
        self.assertEqual(self.saved, [])
        self.assertEqual(self.online.skill_proficiencies["Shadow Clone Jutsu"], 20)

    def test_failed_save_restores_live_changes(self):
        with patch("immortal_practice.storage.save_player",
                   side_effect=OSError("disk read-only")):
            immortal_practice.command(self.actor, ["shadow", "clone", "50"])
        self.assertEqual(self.offline.skill_proficiencies["Shadow Clone Jutsu"], 4)
        self.assertEqual(self.online.skill_proficiencies["Shadow Clone Jutsu"], 20)
        self.assertEqual(self.online.practiced_skills, [])
        self.assertTrue(any("2 save failure(s)" in call.args[0]
                            for call in self.actor.send.call_args_list))


if __name__ == "__main__":
    unittest.main()
