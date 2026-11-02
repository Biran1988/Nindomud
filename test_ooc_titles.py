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

    def test_setting_next_title_replaces_old_without_clearing(self):
        commands.dispatch(self.session, "title", ["The", "Last", "Uchiha"])
        commands.dispatch(self.session, "title", ["color", "cyan"])
        commands.dispatch(self.session, "title", ["The", "Silent", "Storm"])
        self.assertEqual(self.player.ooc_title, "The Silent Storm")
        self.assertEqual(self.player.ooc_title_color, "cyan")
        self.assertIn("WHO title replaced:", self.session.send.call_args.args[0])
        self.assertNotIn("The Last Uchiha", self.session.send.call_args.args[0])
        saved = storage.load_player("Shinobi")
        self.assertEqual(saved.ooc_title, "The Silent Storm")
        self.assertEqual(saved.ooc_title_color, "cyan")
        self.assertEqual(colors.render(ooc_titles.player_display(saved), False),
                         "Shinobi [The Silent Storm]")

    def test_multicolor_title_uses_inline_mud_codes_and_keeps_color_on_replacement(self):
        commands.dispatch(self.session, "title", ["set", "Initial"])
        commands.dispatch(self.session, "title", ["color", "gold"])
        commands.dispatch(self.session, "title",
                          ["&RFlame", "&CIce", "&[208]Storm"])
        self.assertEqual(self.player.ooc_title, "&RFlame &CIce &[208]Storm")
        self.assertEqual(self.player.ooc_title_color, "gold")
        result = ooc_titles.player_display(self.player)
        plain = colors.render(result, False)
        self.assertEqual(plain, "Shinobi [Flame Ice Storm]")
        colored = colors.render(result, True)
        self.assertIn("\x1b[1;31m", colored)  # bright red
        self.assertIn("\x1b[36m", colored)    # cyan
        self.assertIn("\x1b[38;5;208m", colored)  # xterm orange
        self.assertLess(colored.index("\x1b[1;31m"),
                        colored.index("\x1b[36m"))
        self.assertLess(colored.index("\x1b[36m"),
                        colored.index("\x1b[38;5;208m"))
        loaded = storage.load_player("Shinobi")
        self.assertEqual(loaded.ooc_title, "&RFlame &CIce &[208]Storm")
        self.assertEqual(colors.render(ooc_titles.player_display(loaded), False),
                         "Shinobi [Flame Ice Storm]")

    def test_titles_never_appear_in_ooc_or_saved_chat_history(self):
        commands.dispatch(self.session, "title", ["The", "Hokage"])
        commands.dispatch(self.session, "title", ["color", "gold"])
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_ooc(self.session, ["hello", "everyone"])
        rendered = self.session.broadcast_all.call_args.args[0]
        self.assertIn("[OOC] Shinobi: hello everyone", colors.render(rendered, False))
        self.assertNotIn("Hokage", rendered)
        self.assertIn("[OOC] You: hello everyone",
                      colors.render(self.session.send.call_args.args[0], False))
        self.assertEqual(list(chatlog.ENTRIES),
                         [{"speaker": "Shinobi", "message": "hello everyone"}])
        # Old persisted OOC entries with title snapshots must also display
        # without the historical titles. Do not destroy their saved data.
        chatlog.ENTRIES.append({"speaker": "Shinobi", "title": "Old Title",
                                "title_color": "red", "message": "old message"})
        self.session.send.reset_mock()
        commands.cmd_chatlog(self.session, [])
        output = self.session.send.call_args.args[0]
        self.assertIn("[OOC] Shinobi: old message", colors.render(output, False))
        self.assertNotIn("Old Title", output)
        chatlog.ENTRIES.clear()
        chatlog.load_all()
        self.assertEqual(chatlog.ENTRIES[0]["message"], "hello everyone")

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
        for value in ("&QAdministrator", "\x1b[31mEvil", "[OOC]", "X" * 41,
                      "&[256]Fake", "&[999]Fake", "&xReset", "&R" * 17 + "Name",
                      "&R" + "X" * 41):
            commands.dispatch(self.session, "title", [value])
            self.assertEqual(self.player.ooc_title, "")
        commands.dispatch(self.session, "title", ["Good", "Ninja"])
        commands.dispatch(self.session, "title", ["color", "256"])
        self.assertEqual(self.player.ooc_title_color, "gold")
        commands.dispatch(self.session, "title", ["color", "&R"])
        self.assertEqual(self.player.ooc_title_color, "gold")

    def test_ooc_emotes_never_include_titles(self):
        self.player.ooc_title = "The Wanderer"
        self.player.ooc_title_color = "cyan"
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_emote(self.session, ["@yawn"], ooc=True)
        self.assertIn("[OOC]", self.session.broadcast_all.call_args.args[0])
        self.assertIn("Shinobi yawns.", self.session.broadcast_all.call_args.args[0])
        self.assertNotIn("Wanderer", self.session.broadcast_all.call_args.args[0])
        self.assertEqual(chatlog.ENTRIES[0],
                         {"speaker": "Shinobi", "message": "[emote] yawns."})
        self.session.broadcast_all.reset_mock()
        self.session.broadcast_room = Mock()
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_emote(self.session, ["@yawn"], ooc=False)
        self.assertIn("Shinobi yawns.", self.session.broadcast_room.call_args.args[0])
        self.assertNotIn("The Wanderer", self.session.broadcast_room.call_args.args[0])

    def test_title_only_in_who_not_whois_score_or_look(self):
        import world
        self.player.ooc_title = "The Last Uchiha"
        self.player.ooc_title_color = "208"
        self.player.primary_class = "ninjutsu"
        self.player.room_vnum = 5001

        viewer = Player("Observer", "Observer")
        viewer.village = "leaf"
        viewer.primary_class = "ninjutsu"
        viewer.room_vnum = 5001
        observer = NS(player=viewer, account=NS(staff_level="player"), send=Mock(),
                      _clone_original_player=None)
        observer.active_sessions = lambda: [observer, self.session]
        self.session.active_sessions = observer.active_sessions
        with patch("staff_invisibility.visible_to", return_value=True):
            commands.cmd_who(observer, [])
            output = observer.send.call_args.args[0]
            self.assertIn("Shinobi &[208][The Last Uchiha]&x", output)
            observer.send.reset_mock()
            commands.cmd_whois(observer, ["Shinobi"])
            output = observer.send.call_args.args[0]
            self.assertIn("Shinobi", output)
            self.assertNotIn("The Last Uchiha", output)

        score = "\n".join(commands.build_score_lines(self.player, "Nobody"))
        self.assertIn("Name:", score)
        self.assertIn("Shinobi", score)
        self.assertNotIn("The Last Uchiha", score)

        room = world.Room(5001, "Test Clearing", "Open ground.")
        with (patch.object(commands.WORLD, "get", return_value=room),
              patch.object(commands, "_format_exits", return_value=[]),
              patch.object(commands, "_player_hidden_from", return_value=False),
              patch("seasonal_events.tree_visible", return_value=False),
              patch("halloween_event.decorate_village", return_value=""),
              patch("combat.mobs_in_room", return_value=[]),
              patch("corpses.corpses_in_room", return_value=[]),
              patch("room_jutsu_objects.active_objects", return_value=[]),
              patch("genjutsu.decoys_in_room", return_value=[]),
              patch("session.ACTIVE_SESSIONS", [])):
            commands.cmd_look(observer, [])
            rendered = colors.render(observer.send.call_args.args[0], False)
            self.assertIn("Shinobi is here.", rendered)
            self.assertNotIn("The Last Uchiha", rendered)
            commands.cmd_look(observer, ["Shinobi"])
            self.assertIn("Shinobi", observer.send.call_args.args[0])
            self.assertNotIn("The Last Uchiha", observer.send.call_args.args[0])

        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_ooc(self.session, ["hello"])
        self.assertNotIn("The Last Uchiha", self.session.broadcast_all.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
