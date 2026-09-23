"""Isolated social tests: no area loading or persistent file writes."""
import time
import unittest
from unittest.mock import patch

import commands
import emotes
from models import Player
from session import Session, State


class EmoteTests(unittest.TestCase):
    def setUp(self):
        self.sessions_patch = patch("session.ACTIVE_SESSIONS", [])
        self.sessions_patch.start()
        self.addCleanup(self.sessions_patch.stop)
        self.log_patch = patch("chatlog.record")
        self.log = self.log_patch.start()
        self.addCleanup(self.log_patch.stop)
        self.actor, self.own = self.make_session("Brian", 1)
        self.near, self.local = self.make_session("Nearby", 1)
        self.far, self.remote = self.make_session("Distant", 2)

    def make_session(self, name, room):
        output = []
        session = Session(output.append, lambda: None)
        session.player = Player(name=name, account_name=name)
        session.player.room_vnum = room
        session.state = State.PLAYING
        session.color_enabled = False
        output.clear()
        return session, output

    def test_room_only(self):
        commands.dispatch_line(self.actor, "@YaWn")
        self.assertIn("You yawn.", "".join(self.own))
        self.assertIn("Brian yawns.", "".join(self.local))
        self.assertEqual(self.remote, [])
        self.log.assert_not_called()

    def test_ooc_global_and_logged(self):
        commands.dispatch_line(self.actor, "ooc @yawn")
        self.assertIn("[OOC] You yawn.", "".join(self.own))
        for output in (self.local, self.remote):
            self.assertIn("[OOC] Brian yawns.", "".join(output))
        self.log.assert_called_once_with("Brian", "[emote] yawns.")

    def test_all_emotes_both_channels(self):
        self.assertGreaterEqual(len(emotes.EMOTES), 75)
        for name, (own, other) in emotes.EMOTES.items():
            for prefix in ("", "ooc "):
                with self.subTest(name=name, channel=prefix):
                    self.own.clear()
                    self.local.clear()
                    self.remote.clear()
                    self.actor.recent_chat_times.clear()
                    commands.dispatch_line(self.actor, prefix + "@" + name)
                    self.assertIn("You " + own, "".join(self.own))
                    self.assertIn("Brian " + other, "".join(self.local))
                    self.assertEqual(bool(self.remote), bool(prefix))

    def test_invalid_input_is_not_broadcast(self):
        for command in ("@", "@notreal", "@yawn Brian", "ooc @notreal", "ooc @yawn extra"):
            commands.dispatch_line(self.actor, command)
        self.assertEqual(self.local, [])
        self.assertEqual(self.remote, [])
        self.log.assert_not_called()
        self.assertEqual(self.actor.recent_chat_times, [])

    def test_silence_blocks_both_channels(self):
        self.actor.player.silenced_until = time.time() + 600
        for command in ("@yawn", "ooc @yawn"):
            commands.dispatch_line(self.actor, command)
        self.assertEqual(self.local, [])
        self.assertEqual(self.remote, [])
        self.log.assert_not_called()
        self.assertIn("silenced", "".join(self.own))

    def test_spam_limit_shared_between_channels(self):
        with patch("chat_moderation.time.time", return_value=1000):
            for command in ("@yawn", "ooc @yawn") * 3:
                commands.dispatch_line(self.actor, command)
        self.assertEqual(len(self.local), 5)
        self.assertEqual(len(self.remote), 2)
        self.assertEqual(self.actor.player.silenced_until, 1600)

    def test_ordinary_ooc_unchanged(self):
        commands.dispatch_line(self.actor, "ooc hello everyone")
        self.assertIn("[OOC] Brian: hello everyone", "".join(self.remote))
        self.log.assert_called_once_with("Brian", "hello everyone")

    def test_catalog_is_paginated_and_complete(self):
        with patch.object(self.actor, "send_paginated") as show:
            commands.dispatch_line(self.actor, "emotes")
        text = show.call_args.args[0]
        for name in emotes.EMOTES:
            self.assertIn("@" + name, text)
        self.assertIn("ooc @yawn", text)

    def test_room_emotes_respect_existing_action_restrictions(self):
        self.actor.player.downed_by = "Opponent"
        commands.dispatch_line(self.actor, "@yawn")
        self.assertEqual(self.local, [])


if __name__ == "__main__":
    unittest.main()
