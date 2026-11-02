"""Player-defined colored OOC titles: persistence, formatting and safety."""
from collections import deque
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import tempfile
import unittest

import chatlog
import commands
import colors
import ooc_titles
import storage
from models import Player


class OocTitleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir_patch = patch.object(storage, "DATA_DIR", self.temp.name)
        self.dir_patch.start()
        self.addCleanup(self.dir_patch.stop)
        self.entries_patch = patch.object(chatlog, "ENTRIES", deque(maxlen=25))
        self.entries_patch.start()
        self.addCleanup(self.entries_patch.stop)
        self.player = Player("Shinobi", "Shinobi")
        self.player.village = "leaf"
        self.session = NS(player=self.player, send=Mock(),
                          broadcast_all=Mock(), recent_chat_times=[])

    def test_title_command_sets_color_and_persists_in_player_save(self):
        commands.dispatch(self.session, "title", ["The", "Last", "Uchiha"])
        commands.dispatch(self.session, "title", ["color", "208"])
        self.assertEqual(self.player.ooc_title, "The Last Uchiha")
        self.assertEqual(self.player.ooc_title_color, "208")
        self.assertEqual(self.player.name, "Shinobi")
        loaded = storage.load_player("Shinobi")
        self.assertIsNotNone(loaded)
        self.assertEqual((loaded.ooc_title, loaded.ooc_title_color),
                         ("The Last Uchiha", "208"))
        self.assertEqual(loaded.name, "Shinobi")
        self.assertEqual(colors.render(ooc_titles.player_display(loaded), False),
                         "Shinobi [The Last Uchiha]")
        self.assertIn("\x1b[38;5;208m", colors.render(ooc_titles.player_display(loaded), True))

    def test_active_title_in_ooc_and_saved_chat_history(self):
        commands.dispatch(self.session, "title", ["set", "The", "Hokage"])
        commands.dispatch(self.session, "title", ["color", "gold"])
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_ooc(self.session, ["hello", "everyone"])
        text = self.session.broadcast_all.call_args.args[0]
        self.assertIn("&[220][The Hokage]&x:", text)
        self.assertIn("Shinobi", text)
        self.assertIn("Shinobi", self.session.send.call_args.args[0] if self.session.send.call_args else "")
        self.assertEqual(len(chatlog.ENTRIES), 1)
        self.assertEqual(chatlog.ENTRIES[0]["title"], "The Hokage")
        self.assertEqual(chatlog.ENTRIES[0]["title_color"], "gold")
        self.session.send.reset_mock()
        commands.cmd_chatlog(self.session, [])
        self.assertIn("[The Hokage]", self.session.send.call_args.args[0])
        chatlog.ENTRIES.clear()
        chatlog.load_all()
        self.assertEqual(chatlog.ENTRIES[0]["title"], "The Hokage")

    def test_legacy_ooc_without_title_stays_the_same(self):
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_ooc(self.session, ["hello"])
        self.assertEqual(chatlog.ENTRIES[0], {"speaker": "Shinobi", "message": "hello"})
        self.assertIn("[OOC] Shinobi:", self.session.broadcast_all.call_args.args[0])
        self.session.send.reset_mock()
        commands.cmd_chatlog(self.session, [])
        self.assertIn("[OOC] Shinobi:", self.session.send.call_args.args[0])

    def test_title_remove_reverts_ooc_output_and_keeps_color_choice(self):
        commands.dispatch(self.session, "title", ["Wolf", "of", "Konoha"])
        commands.dispatch(self.session, "title", ["color", "purple"])
        commands.dispatch(self.session, "title", ["clear"])
        self.assertEqual(self.player.ooc_title, "")
        self.assertEqual(self.player.ooc_title_color, "purple")
        self.assertEqual(ooc_titles.player_display(self.player), "Shinobi")
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_ooc(self.session, ["back"])
        self.assertNotIn("Wolf", self.session.broadcast_all.call_args.args[0])

    def test_invalid_title_and_color_cannot_inject_codes(self):
        for value in ("&RAdministrator", "\x1b[31mEvil", "[OOC]", "X" * 41):
            commands.dispatch(self.session, "title", [value])
            self.assertEqual(self.player.ooc_title, "")
        commands.dispatch(self.session, "title", ["Good", "Ninja"])
        commands.dispatch(self.session, "title", ["color", "256"])
        self.assertEqual(self.player.ooc_title_color, "gold")
        commands.dispatch(self.session, "title", ["color", "&R"])
        self.assertEqual(self.player.ooc_title_color, "gold")

    def test_emotes_show_title_only_on_ooc_channel(self):
        self.player.ooc_title = "The Wanderer"
        self.player.ooc_title_color = "cyan"
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_emote(self.session, ["@yawn"], ooc=True)
        self.assertIn("[The Wanderer]", self.session.broadcast_all.call_args.args[0])
        self.assertEqual(chatlog.ENTRIES[0]["title"], "The Wanderer")
        self.session.broadcast_all.reset_mock()
        self.session.broadcast_room = Mock()
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_emote(self.session, ["@yawn"], ooc=False)
        self.assertIn("Shinobi yawns.", self.session.broadcast_room.call_args.args[0])
        self.assertNotIn("The Wanderer", self.session.broadcast_room.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
