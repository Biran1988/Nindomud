import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import corpses
import leveling
import olc
import world
import clone_control
from models import Player


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.origin = world.Room(97001, "Road", "A road")
        self.target = world.Room(97002, "Courtyard", "A courtyard")
        self.origin.exits["north"] = self.target.vnum
        self.target.ground_items = ["Visible Kunai", "Invisible Scroll"]
        self.player = Player("Scout", "Scout", level=3, room_vnum=self.origin.vnum,
                             learned_skills=["Scan"], skill_proficiencies={"Scan": 100})
        self.other = NS(player=NS(name="Friend", room_vnum=self.target.vnum,
                                  active_status_effects={}))
        self.invisible_player = NS(player=NS(name="Ghost", room_vnum=self.target.vnum,
                                            active_status_effects={"invisible": {}}))
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          send=Mock(), active_sessions=lambda: [self.other, self.invisible_player])
        visible = combat.Mob(1, 97003, "visible guard", 1, 10, 10, self.target.vnum, 0, 0)
        hidden = combat.Mob(2, 97004, "invisible guard", 1, 10, 10, self.target.vnum, 0, 0)
        objects = {
            97005: olc.default_object(97005, "Visible Kunai"),
            97006: olc.default_object(97006, "Invisible Scroll"),
        }
        objects[97006]["extra_flags"] = ["invis"]
        for target, value in [
            ("world.WORLD.rooms", {self.origin.vnum: self.origin, self.target.vnum: self.target}),
            ("combat.MOBS_BY_ROOM", {self.target.vnum: [visible, hidden]}),
            ("combat.MOB_TEMPLATES", {97003: combat.default_template(97003, "visible guard"),
                                       97004: {**combat.default_template(97004, "invisible guard"), "act_flags": ["Invis"]}}),
            ("olc.OBJECT_TEMPLATES", objects),
            ("corpses.CORPSES_BY_ROOM", {self.target.vnum: [corpses.Corpse("a fallen guard", self.target.vnum)]}),
        ]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def test_scan_lists_entire_adjacent_room_except_invisible_targets(self):
        commands.cmd_scan(self.session, ["n"])
        shown = self.session.send.call_args.args[0]
        for name in ("Courtyard", "Friend", "visible guard", "Visible Kunai", "a fallen guard"):
            self.assertIn(name, shown)
        for name in ("Ghost", "invisible guard", "Invisible Scroll"):
            self.assertNotIn(name, shown)
        self.assertEqual(self.player.room_vnum, self.origin.vnum)

    def test_level_and_closed_or_hidden_exit_block_scan(self):
        self.player.level = 2
        commands.cmd_scan(self.session, ["north"])
        self.assertIn("level 3", self.session.send.call_args.args[0])
        self.player.level = 3
        self.origin.exit_flags["north"] = ["door"]
        commands.cmd_scan(self.session, ["north"])
        self.assertIn("closed", self.session.send.call_args.args[0])
        self.origin.exit_flags["north"] = ["hidden"]
        commands.cmd_scan(self.session, ["north"])
        self.assertNotIn("Courtyard", self.session.send.call_args.args[0])

    def test_real_scan_gains_match_jutsu_rules_and_award_xp(self):
        for start, result, xp in ((7, 9, 20), (70, 72, 20), (99, 100, 10), (100, 100, 0)):
            with self.subTest(start=start):
                self.player.skill_proficiencies["Scan"] = start
                before = self.player.experience
                with patch.object(combat.random, "randint", return_value=1):
                    commands.cmd_scan(self.session, ["north"])
                self.assertEqual(self.player.skill_proficiencies["Scan"], result)
                self.assertEqual(self.player.experience - before, xp)
        self.player.skill_proficiencies["Scan"] = 70
        with patch.object(combat.random, "randint", return_value=100):
            commands.cmd_scan(self.session, ["north"])
        self.assertEqual(self.player.skill_proficiencies["Scan"], 70)

    def test_invalid_or_unpracticed_scans_do_not_grant_growth(self):
        self.player.skill_proficiencies["Scan"] = 7
        with patch.object(combat, "grow_skill_from_usage") as grow:
            for args in ([], ["bad"], ["south"]):
                commands.cmd_scan(self.session, args)
            self.origin.exit_flags["north"] = ["door"]
            commands.cmd_scan(self.session, ["north"])
            self.origin.exit_flags.clear()
            self.player.practice_gate_enabled = True
            commands.cmd_scan(self.session, ["north"])
            grow.assert_not_called()

    def test_clone_scan_awards_xp_to_real_body_without_moving_it(self):
        self.player.skill_proficiencies["Scan"] = 50
        self.player.room_vnum = 97010
        self.session.controlled_clone = NS(room_vnum=self.origin.vnum)
        before = self.player.experience
        with patch.object(combat.random, "randint", return_value=1):
            clone_control._sense(self.session, "scan", ["north"])
        self.assertIs(self.session.player, self.player)
        self.assertEqual(self.player.room_vnum, 97010)
        self.assertEqual(self.player.skill_proficiencies["Scan"], 52)
        self.assertEqual(self.player.experience - before, 20)

    def test_scan_is_level_three_general_skill(self):
        self.assertEqual(commands._skill_unlock_level("Scan"), leveling.SCAN_LEVEL)
        self.assertIn(("Scan", 3), commands._skill_catalog_for_category("General Skills"))


if __name__ == "__main__":
    unittest.main()
