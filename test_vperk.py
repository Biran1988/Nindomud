"""Immortal-controlled, persisted, MUD-wide 24-hour perk overrides."""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import storage
import village_perks
from data_villages import VILLAGES
from models import Player


class ImmortalVillagePerkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patches = [
            patch.object(storage, "DATA_DIR", self.temp.name),
            patch.object(village_perks, "_ACTIVE_PERKS", {}),
            patch.object(village_perks, "_STAFF_PERKS", {}),
            patch.object(village_perks, "_STAFF_LOADED_PATH", None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.player = Player("ImmortalTester", "ImmortalTester")
        self.player.village = "leaf"
        self.player.mission_points = 5
        self.account = NS(staff_level="helper")
        self.session = NS(player=self.player, account=self.account,
                          send=Mock(), broadcast_village=Mock())

    def test_non_immortals_cannot_grant_or_revoke_perks(self):
        self.account.staff_level = "player"
        commands.dispatch(self.session, "vperk", ["double", "exp", "on"])
        self.assertIn("Only immortals", self.session.send.call_args.args[0])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 1.0)
        self.assertFalse(os.path.isfile(os.path.join(self.temp.name, "village_perks.json")))

    def test_enable_perk_for_24_hours_without_spending_mission_points(self):
        before = village_perks.time.time()
        commands.dispatch(self.session, "vperk", ["double", "exp", "on"])
        for village in VILLAGES:
            self.assertEqual(village_perks.xp_multiplier(village), 2.0)
        self.assertEqual(self.player.mission_points, 5)
        self.assertEqual(self.session.broadcast_village.call_count, len(VILLAGES))
        self.assertIn("24 hours", self.session.send.call_args.args[0])
        path = os.path.join(self.temp.name, "village_perks.json")
        with open(path, encoding="utf-8") as handle:
            entry = json.load(handle)["all"]["exp"]
        self.assertEqual(entry["perk"], "double exp")
        self.assertGreaterEqual(entry["expires_at"] - before, 86399)
        self.assertLessEqual(entry["expires_at"] - before, 86410)

    def test_override_survives_restart_and_expires_after_24_hours(self):
        with patch.object(village_perks.time, "time", return_value=1_800_000_000.0):
            commands.cmd_vperk(self.session, ["double", "damage", "on"])
            self.assertEqual(village_perks.damage_multiplier("leaf"), 2.0)
            self.assertEqual(village_perks.damage_multiplier("sand"), 2.0)
        village_perks._STAFF_PERKS.clear()
        village_perks._STAFF_LOADED_PATH = None  # Simulate importing on server boot.
        with patch.object(village_perks.time, "time", return_value=1_800_086_399.0):
            self.assertEqual(village_perks.damage_multiplier("leaf"), 2.0)
        with patch.object(village_perks.time, "time", return_value=1_800_086_400.0):
            self.assertEqual(village_perks.damage_multiplier("leaf"), 1.0)

    def test_disable_specific_staff_perk_does_not_cancel_other_categories(self):
        commands.cmd_vperk(self.session, ["double", "exp", "on"])
        commands.cmd_vperk(self.session, ["triple", "ryo", "on"])
        commands.cmd_vperk(self.session, ["double", "exp", "off"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 1.0)
        self.assertEqual(village_perks.ryo_multiplier("leaf"), 3.0)
        self.assertIn("disabled", self.session.send.call_args.args[0])
        commands.cmd_vperk(self.session, ["double", "exp", "off"])
        self.assertIn("not the active immortal perk", self.session.send.call_args.args[0])

    def test_in_category_new_perk_replaces_old_and_old_off_cannot_clear_new(self):
        commands.cmd_vperk(self.session, ["double", "exp", "on"])
        commands.cmd_vperk(self.session, ["triple", "exp", "on"])
        commands.cmd_vperk(self.session, ["double", "exp", "off"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 3.0)
        commands.cmd_vperk(self.session, ["triple", "exp", "off"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 1.0)

    def test_kage_perks_still_work_and_override_only_during_24h(self):
        village_perks.purchase("leaf", "double exp")
        self.assertEqual(village_perks.xp_multiplier("leaf"), 2.0)
        commands.cmd_vperk(self.session, ["triple", "exp", "on"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 3.0)
        commands.cmd_vperk(self.session, ["triple", "exp", "off"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 2.0)
        self.assertEqual(village_perks.duration_seconds("double exp"), 3600)

    def test_triple_exp_perk_applies_to_job_actions_only_while_active(self):
        import jobs
        for job in ("fishing", "mining", "lumberjack", "farming", "cooking", "gemcutter"):
            player = Player("Worker", "Worker")
            player.village = "sand"
            session = NS(player=player, send=Mock())
            with self.subTest(job=job):
                # No perk: original profession XP, including when off again.
                commands._award_job_action_xp(session, job, 20)
                self.assertEqual(jobs.get_job_xp(player, job), 20)

                commands.cmd_vperk(self.session, ["triple", "exp", "on"])
                commands._award_job_action_xp(session, job, 20)
                self.assertEqual(jobs.get_job_xp(player, job), 80)
                self.assertTrue(any("+60 " + job.capitalize() + " XP" in m.args[0]
                                    for m in session.send.call_args_list))
                commands.cmd_vperk(self.session, ["triple", "exp", "off"])
                commands._award_job_action_xp(session, job, 20)
                self.assertEqual(jobs.get_job_xp(player, job), 100)

    def test_job_xp_perk_persists_across_reboot_and_stops_on_expiry(self):
        import jobs
        player = Player("Gatherer", "Gatherer")
        player.village = "cloud"
        session = NS(player=player, send=Mock())
        base_time = 1_800_000_000.0
        with patch.object(village_perks.time, "time", return_value=base_time):
            commands.cmd_vperk(self.session, ["triple", "exp", "on"])
            commands._award_job_action_xp(session, "fishing", 15)
            self.assertEqual(jobs.get_job_xp(player, "fishing"), 45)
        village_perks._STAFF_PERKS.clear()
        village_perks._STAFF_LOADED_PATH = None
        with patch.object(village_perks.time, "time", return_value=base_time + 86399):
            commands._award_job_action_xp(session, "fishing", 15)
            self.assertEqual(jobs.get_job_xp(player, "fishing"), 90)
        with patch.object(village_perks.time, "time", return_value=base_time + 86400):
            commands._award_job_action_xp(session, "fishing", 15)
            self.assertEqual(jobs.get_job_xp(player, "fishing"), 105)

    def test_global_bonuses_affect_every_village_and_status(self):
        commands.cmd_vperk(self.session, ["double", "ryo", "on"])
        for village in VILLAGES:
            self.assertEqual(village_perks.ryo_multiplier(village), 2.0)
        self.assertEqual(self.session.broadcast_village.call_count, len(VILLAGES))
        commands.cmd_vperk(self.session, ["status"])
        self.assertIn("Immortal perks (entire MUD)", self.session.send.call_args.args[0])
        self.assertIn("Double Ryo", self.session.send.call_args.args[0])
        commands.cmd_vperk(self.session, ["double", "ryo", "off"])
        for village in VILLAGES:
            self.assertEqual(village_perks.ryo_multiplier(village), 1.0)

    def test_alias_and_leading_action(self):
        commands.dispatch(self.session, "villageperk", ["on", "double", "damage"])
        self.assertEqual(village_perks.damage_multiplier("leaf"), 2.0)

    def test_local_village_target_is_not_supported_for_immortal_perks(self):
        commands.cmd_vperk(self.session, ["leaf", "double", "exp", "on"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 1.0)
        self.assertIn("MUD-wide", self.session.send.call_args.args[0])

    def test_invalid_village_or_perk_cannot_change_state(self):
        commands.cmd_vperk(self.session, ["moon", "double", "exp", "on"])
        self.assertIn("Unknown village perk", self.session.send.call_args.args[0])
        commands.cmd_vperk(self.session, ["infinite", "exp", "on"])
        self.assertIn("Unknown village perk", self.session.send.call_args.args[0])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 1.0)

    def test_failed_save_rolls_back_status_and_does_not_broadcast(self):
        with patch.object(village_perks, "_save_staff_perks", side_effect=OSError("full disk")):
            commands.cmd_vperk(self.session, ["double", "exp", "on"])
        self.assertEqual(village_perks.xp_multiplier("leaf"), 1.0)
        self.assertIn("Failed to save", self.session.send.call_args.args[0])
        self.session.broadcast_village.assert_not_called()


if __name__ == "__main__":
    unittest.main()
