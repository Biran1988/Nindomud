"""Safe player command forcing from immortals and SMAUG mob programs."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import force_commands
import smaug_progs


def fake_session(name, rank="player", state="PLAYING"):
    return NS(
        player=NS(name=name, room_vnum=1), account=NS(name=name, staff_level=rank),
        state=NS(name=state), send=Mock(), send_prompt=Mock(),
    )


class ForceCommandsTests(unittest.TestCase):
    def setUp(self):
        self.imm = fake_session("Biran", "implementor")
        self.player = fake_session("Sakura")
        self.another = fake_session("Naruto")
        self.helper = fake_session("Iruka", "helper")
        self.builder = fake_session("Asuma", "builder")
        sessions = [self.imm, self.player, self.another, self.helper, self.builder]
        for session in sessions:
            session.active_sessions = lambda sessions=sessions: sessions
        self.dispatch_patch = patch.object(commands, "dispatch_line")
        self.dispatch = self.dispatch_patch.start()
        self.addCleanup(self.dispatch_patch.stop)
        self.log_patch = patch.object(commands.olc, "_log")
        self.log = self.log_patch.start()
        self.addCleanup(self.log_patch.stop)

    def test_immortal_forces_an_online_character_to_move(self):
        commands.cmd_force(self.imm, ["Sakura", "north"])
        self.dispatch.assert_called_once_with(self.player, "north")
        self.assertIn("forces you", self.player.send.call_args.args[0])
        self.player.send_prompt.assert_called_once()
        self.assertIn("Forced 1 character", self.imm.send.call_args.args[0])
        self.log.assert_called_once()
        self.assertEqual(getattr(self.player, "_force_command_depth"), 0)

    def test_helper_can_force_player_but_never_staff(self):
        commands.cmd_force(self.helper, ["Naruto", "say", "Hello", "world"])
        self.dispatch.assert_called_once_with(self.another, "say Hello world")
        self.dispatch.reset_mock()
        commands.cmd_force(self.helper, ["Asuma", "look"])
        self.dispatch.assert_not_called()
        self.assertIn("Staff characters cannot be forced", self.helper.send.call_args.args[0])

    def test_players_cannot_use_force(self):
        commands.cmd_force(self.player, ["Naruto", "north"])
        self.dispatch.assert_not_called()
        self.assertIn("Only immortals", self.player.send.call_args.args[0])

    def test_refuses_sensitive_commands_before_dispatch(self):
        for verb in ("force", "password", "quit", "drop all", "give gold Biran",
                     "makeimm Naruto", "mset 50 level 100", "promoteimm",
                     "trade Naruto", "bank withdraw 10000", "reboot",
                     "hedit edit test", "setkage Naruto", "rset create",
                     "save world"):
            commands.cmd_force(self.imm, ["Sakura"] + verb.split())
            self.dispatch.assert_not_called()
        self.assertIn("cannot be forced", self.imm.send.call_args.args[0])

    def test_force_all_only_allows_admin_social_actions_and_skips_staff(self):
        commands.cmd_force(self.helper, ["all", "look"])
        self.dispatch.assert_not_called()
        self.assertIn("Only administrators", self.helper.send.call_args.args[0])
        commands.cmd_force(self.imm, ["all", "north"])
        self.dispatch.assert_not_called()
        self.assertIn("limited", self.imm.send.call_args.args[0])
        commands.cmd_force(self.imm, ["all", "say", "Academy", "is", "open"])
        self.assertEqual(self.dispatch.call_count, 2)
        self.assertEqual({c.args[0].player.name for c in self.dispatch.call_args_list},
                         {"Sakura", "Naruto"})
        self.assertTrue(all(c.args[1] == "say Academy is open"
                            for c in self.dispatch.call_args_list))

    def test_rejects_offline_ambiguous_and_editing_targets(self):
        commands.cmd_force(self.imm, ["Unknown", "look"])
        self.dispatch.assert_not_called()
        self.player.state.name = "EDITING"
        commands.cmd_force(self.imm, ["Sakura", "look"])
        self.dispatch.assert_not_called()

    def test_recursive_forcing_is_blocked(self):
        def recursive(target, text):
            ok, error = force_commands.run_forced_player_command(
                target, "say A repeated command", "Examiner")
            self.assertFalse(ok)
            self.assertIn("already executing", error)
        self.dispatch.side_effect = recursive
        commands.cmd_force(self.imm, ["Sakura", "look"])
        self.assertEqual(self.dispatch.call_count, 1)
        self.assertEqual(self.player._force_command_depth, 0)

    def test_native_emotes_are_forced_through_real_dispatch(self):
        commands.cmd_force(self.imm, ["Sakura", "emote", "yawn"])
        self.dispatch.assert_called_once_with(self.player, "@yawn")
        self.dispatch.reset_mock()
        commands.cmd_force(self.imm, ["Sakura", "@smile"])
        self.dispatch.assert_called_once_with(self.player, "@smile")
        self.dispatch.reset_mock()
        commands.cmd_force(self.imm, ["Sakura", "emote", "unknown"])
        self.dispatch.assert_not_called()

    def test_mpforce_accepts_smaug_target_and_legacy_format(self):
        self.assertEqual(smaug_progs.validate_script("mpforce $n north"), [])
        self.assertEqual(smaug_progs.validate_script("mpforce $n say Greetings."), [])
        self.assertEqual(smaug_progs.validate_script("mpforce say Greetings."), [])
        for invalid in ("mpforce $n makeimm Naruto", "mpforce all say hi",
                        "mpforce $n password secret", "mpforce $n force Naruto north",
                        "mpforce $n drop all", "mpforce staff look"):
            self.assertTrue(smaug_progs.validate_script(invalid), invalid)

    def test_mpforce_uses_triggering_player_real_command(self):
        self.assertTrue(smaug_progs.execute(
            "mpforce $n say Welcome to the academy.",
            self.player, speaker_name="Examiner"))
        self.dispatch.assert_called_once_with(self.player, "say Welcome to the academy.")
        self.assertIn("Examiner forces you", self.player.send.call_args.args[0])
        self.dispatch.reset_mock()
        self.assertTrue(smaug_progs.execute("mpforce north", self.player, "Examiner"))
        self.dispatch.assert_called_once_with(self.player, "north")

    def test_legacy_mpforce_custom_emote_still_narrates_without_dispatch(self):
        self.assertEqual(smaug_progs.validate_script(
            "mpforce emote raises a hand in greeting."), [])
        with patch.object(smaug_progs, "_broadcast") as broadcast:
            self.assertTrue(smaug_progs.execute(
                "mpforce emote raises a hand in greeting.",
                self.player, "Examiner"))
            broadcast.assert_called_once_with(
                self.player, "Sakura raises a hand in greeting.")
        self.dispatch.assert_not_called()

    def test_mpforce_does_not_force_staff_triggering_player(self):
        self.assertTrue(smaug_progs.execute(
            "mpforce $n say Test", self.imm, "Examiner"))
        self.dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
