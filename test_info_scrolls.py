"""Info Scroll editor, individual notes, trading and restart safety."""
import os
import tempfile
import unittest
from unittest.mock import patch

import commands
import content
import inventory
import olc
import scroll_writing
import storage
import world
from models import Player
from session import ACTIVE_SESSIONS, Session, State


class InfoScrollTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = patch.object(storage, "DATA_DIR", self.temp.name)
        settings.start()
        self.addCleanup(settings.stop)
        templates = patch.object(olc, "OBJECT_TEMPLATES", {
            9811: dict(olc.default_object(9811, "An Info Scroll"),
                       item_type="scroll", scroll_message_writable=True),
            9771: dict(olc.default_object(9771, "A Track Scroll"),
                       item_type="scroll", scroll_jutsu="track"),
        })
        templates.start()
        self.addCleanup(templates.stop)
        self.room = world.Room(998111, "Scroll workshop", "A writing desk.")
        rooms = patch.object(world.WORLD, "rooms", {self.room.vnum: self.room})
        rooms.start()
        self.addCleanup(rooms.stop)
        self.logs = []
        self.session = Session(self.logs.append, lambda: None)
        self.session.state = State.PLAYING
        self.session.player = Player("Writer", "Writer", room_vnum=self.room.vnum)
        self.session.player.inventory = ["An Info Scroll", "An Info Scroll", "A Track Scroll"]
        self.session.account = type("Account", (), {"staff_level": "player"})()
        player_saver = patch.object(storage, "save_player")
        self.save_player = player_saver.start()
        self.addCleanup(player_saver.stop)
        ACTIVE_SESSIONS.append(self.session)
        self.addCleanup(lambda: ACTIVE_SESSIONS.remove(self.session)
                        if self.session in ACTIVE_SESSIONS else None)

    def _write(self, text, query="info scroll"):
        commands.cmd_write(self.session, query.split())
        self.assertEqual(self.session.state, State.EDITING)
        for line in text.split("\n"):
            self.session._handle_editing(line)
        self.session._handle_editing("/s")
        self.assertEqual(self.session.state, State.PLAYING)

    def test_info_scroll_prototype_separate_from_jutsu_scroll(self):
        self.assertEqual(content._ITEM_VNUMS["info_scroll"], 9811)
        with patch.object(olc, "OBJECT_TEMPLATES", {}):
            content._register_shared_items()
            info = olc.OBJECT_TEMPLATES[9811]
            self.assertEqual(info["item_type"], "scroll")
            self.assertEqual(info["short_desc"], "An Info Scroll")
            self.assertTrue(info["scroll_message_writable"])
            self.assertEqual(info["scroll_jutsu"], "")
            track = olc.OBJECT_TEMPLATES[9771]
            self.assertEqual(track["scroll_jutsu"], "track")
            self.assertFalse(track.get("scroll_message_writable", False))

    def test_multiline_editor_examine_without_examine_skill_and_reboot(self):
        self._write("Hello, traveler!\nFind the hidden waterfall.")
        written = self.session.player.inventory[0]
        self.assertIn("[Written #", written)
        self.assertEqual(self.session.player.inventory[1], "An Info Scroll")
        self.assertEqual(scroll_writing.plain_name(written), "An Info Scroll")
        self.assertEqual(scroll_writing.inscription(written)["author"], "Writer")
        self.assertIn("hidden waterfall", scroll_writing.inscription(written)["text"])
        self.assertTrue(os.path.exists(os.path.join(self.temp.name, "scroll_messages.json")))
        self.assertTrue(self.save_player.called)
        self.assertNotIn("Examine", self.session.player.learned_skills)
        commands.cmd_examine(self.session, ["info", "scroll"])
        self.assertIn("Hello, traveler!", "\n".join(self.logs))
        self.assertIn("Writer", "\n".join(self.logs))
        # Simulate reload from JSON: the visible item identity is saved
        # in the existing player inventory string, the note in data/.
        restored = Player.from_dict(self.session.player.to_dict())
        self.assertEqual(scroll_writing.inscription(restored.inventory[0])["text"],
                         "Hello, traveler!\nFind the hidden waterfall.")

    def test_two_identical_scrolls_keep_distinct_messages(self):
        self._write("First message.")
        first = self.session.player.inventory[0]
        self._write("Second message.", query="2.info scroll")
        second = self.session.player.inventory[1]
        self.assertNotEqual(first, second)
        self.assertEqual(scroll_writing.inscription(first)["text"], "First message.")
        self.assertEqual(scroll_writing.inscription(second)["text"], "Second message.")
        self.assertEqual(scroll_writing.inscription(self.session.player.inventory[2]), None)
        # Rewrite the exact scroll; the other copy must stay unchanged.
        self._write("Revised first message.")
        self.assertEqual(self.session.player.inventory[0], first)
        self.assertEqual(scroll_writing.inscription(first)["text"], "Revised first message.")
        self.assertEqual(scroll_writing.inscription(second)["text"], "Second message.")

    def test_message_follows_scroll_through_give_drop_get(self):
        self._write("For the next ninja.")
        written = self.session.player.inventory[0]
        recipient_logs = []
        recipient = Session(recipient_logs.append, lambda: None)
        recipient.state = State.PLAYING
        recipient.account = self.session.account
        recipient.player = Player("Recipient", "Recipient", room_vnum=self.room.vnum)
        ACTIVE_SESSIONS.append(recipient)
        self.addCleanup(lambda: ACTIVE_SESSIONS.remove(recipient)
                        if recipient in ACTIVE_SESSIONS else None)
        commands.cmd_give(self.session, ["info", "scroll", "Recipient"])
        self.assertIn(written, recipient.player.inventory)
        self.assertNotIn(written, self.session.player.inventory)
        commands.cmd_examine(recipient, ["info", "scroll"])
        self.assertIn("For the next ninja.", "\n".join(recipient_logs))
        commands.cmd_drop(recipient, ["info", "scroll"])
        self.assertIn(written, self.room.ground_items)
        commands.cmd_examine(recipient, ["info", "scroll"])
        self.assertIn("For the next ninja.", "\n".join(recipient_logs))
        commands.cmd_get(recipient, ["info", "scroll"])
        self.assertIn(written, recipient.player.inventory)
        self.assertEqual(scroll_writing.inscription(written)["text"], "For the next ninja.")

    def test_jutsu_scroll_cannot_be_written_and_info_scroll_cannot_teach(self):
        commands.cmd_write(self.session, ["track", "scroll"])
        self.assertEqual(self.session.state, State.PLAYING)
        self.assertIn("not a jutsu-learning scroll", "\n".join(self.logs))
        commands.cmd_read(self.session, ["info", "scroll"])
        self.assertIn("doesn't teach jutsu", "\n".join(self.logs))
        self.assertEqual(len(self.session.player.inventory), 3)

    def test_abort_does_not_assign_an_id(self):
        commands.cmd_write(self.session, ["info", "scroll"])
        self.assertEqual(self.session.state, State.EDITING)
        self.session._handle_editing("An abandoned draft")
        self.session._handle_editing("/a")
        self.assertEqual(self.session.player.inventory[0], "An Info Scroll")
        self.assertIsNone(scroll_writing.inscription("An Info Scroll"))

    def test_no_false_per_instance_metadata_on_other_prototypes(self):
        # Builder-customized object at the reserved VNUM must not be
        # silently changed to writable or stocked as a default info scroll.
        with patch.object(olc, "OBJECT_TEMPLATES", {
            9811: dict(olc.default_object(9811, "Builder's Artifact"),
                       item_type="scroll", scroll_jutsu="track"),
        }):
            content._register_shared_items()
            self.assertEqual(olc.OBJECT_TEMPLATES[9811]["short_desc"],
                             "Builder's Artifact")
            self.assertFalse(olc.OBJECT_TEMPLATES[9811].get("scroll_message_writable"))

    def test_limit_rejects_oversized_text_without_losing_scroll(self):
        with self.assertRaises(ValueError):
            scroll_writing.write("An Info Scroll", "x" * 2501, "Writer")
        self.assertEqual(self.session.player.inventory[0], "An Info Scroll")
        self.assertFalse(scroll_writing.load())


if __name__ == "__main__":
    unittest.main()
