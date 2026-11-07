"""OOC chat output has an empty separator line; stored history stays plain."""
import unittest
from collections import deque
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import chatlog
import commands
from models import Player


class OocSpacingTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("Miko", "miko", village="leaf")
        self.session = NS(player=self.player, send=Mock(),
                          broadcast_all=Mock(), broadcast_room=Mock(),
                          recent_chat_times=[])
        spam = patch("chat_moderation.record_and_check_spam", return_value=False)
        spam.start()
        self.addCleanup(spam.stop)
        saved = patch("chatlog.record")
        self.log = saved.start()
        self.addCleanup(saved.stop)

    def test_ooc_sends_one_blank_line_before_every_post(self):
        for message in ("First post", "Another post"):
            commands.cmd_ooc(self.session, message.split())
            local = self.session.send.call_args.args[0]
            remote = self.session.broadcast_all.call_args.args[0]
            self.assertTrue(local.startswith("\n&M[OOC] You:&x "), local)
            self.assertTrue(remote.startswith("\n&M[OOC] Miko:&x "), remote)
            self.assertIn(message, local)
            self.assertIn(message, remote)
        self.assertEqual(self.log.call_count, 2)
        self.log.assert_any_call("Miko", "First post")
        self.log.assert_any_call("Miko", "Another post")

    def test_ooc_emote_separated_but_in_character_emote_not(self):
        commands.cmd_emote(self.session, ["@yawn"], ooc=True)
        self.assertTrue(self.session.send.call_args.args[0].startswith("\n&M[OOC]"))
        self.assertTrue(self.session.broadcast_all.call_args.args[0].startswith("\n&M[OOC]"))
        self.session.send.reset_mock()
        self.session.broadcast_all.reset_mock()
        commands.cmd_emote(self.session, ["@yawn"], ooc=False)
        self.assertFalse(self.session.send.call_args.args[0].startswith("\n"))
        self.assertFalse(self.session.broadcast_room.call_args.args[0].startswith("\n"))
        self.session.broadcast_all.assert_not_called()

    def test_chatlog_adds_blank_lines_without_mutating_entries(self):
        entries = deque([
            {"speaker": "Miko", "message": "first"},
            {"speaker": "Kinto", "message": "second"},
            {"speaker": "Miko", "message": "third"}
        ], maxlen=25)
        with patch.object(chatlog, "ENTRIES", entries):
            commands.cmd_chatlog(self.session, [])
            output = self.session.send.call_args.args[0]
        self.assertEqual(output,
                         "&M[OOC] Miko:&x first\n\n&M[OOC] Kinto:&x second\n\n"
                         "&M[OOC] Miko:&x third")
        self.assertEqual(entries[0]["message"], "first")
        self.assertEqual(len(entries), 3)

    def test_say_and_village_chat_are_not_given_ooc_spacing(self):
        self.session.broadcast_room.reset_mock()
        commands.cmd_say(self.session, ["Hello"])
        self.assertFalse(self.session.send.call_args.args[0].startswith("\n"))
        self.assertFalse(self.session.broadcast_room.call_args.args[0].startswith("\n"))


if __name__ == "__main__":
    unittest.main()
