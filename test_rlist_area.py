"""Regression tests for RLIST's current-area-only room listing."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import olc


class RlistAreaTests(TestCase):
    def setUp(self):
        self.messages = []
        self.session = SimpleNamespace(
            player=SimpleNamespace(room_vnum=150),
            send=self.messages.append,
        )
        self.area = SimpleNamespace(name="leaf", vnum_start=100, vnum_end=199)
        self.rooms = {
            99: SimpleNamespace(name="Other area before"),
            100: SimpleNamespace(name="Area entrance"),
            150: SimpleNamespace(name="Current room"),
            199: SimpleNamespace(name="Area end"),
            200: SimpleNamespace(name="Other area after"),
        }

    def run_rlist(self, args, area=None):
        with patch.object(olc, "_require_builder", return_value=True), \
             patch.object(olc.world.WORLD, "rooms", self.rooms), \
             patch.object(olc.areas, "find_area_for_vnum", return_value=area):
            olc.cmd_rlist(self.session, args)
        return "\n".join(self.messages)

    def test_rlist_only_displays_rooms_in_current_area(self):
        output = self.run_rlist([], self.area)
        self.assertIn("Rooms in leaf (100-199)", output)
        self.assertIn("100: Area entrance", output)
        self.assertIn("150: Current room", output)
        self.assertIn("199: Area end", output)
        self.assertNotIn("99: Other area before", output)
        self.assertNotIn("200: Other area after", output)

    def test_range_stays_within_current_area(self):
        output = self.run_rlist(["150", "250"], self.area)
        self.assertIn("150: Current room", output)
        self.assertIn("199: Area end", output)
        self.assertNotIn("100: Area entrance", output)
        self.assertNotIn("200: Other area after", output)

    def test_no_registered_area_has_clear_message(self):
        output = self.run_rlist([], None)
        self.assertIn("Room 150 isn't within any registered area.", output)
        self.assertNotIn("Other area", output)

    def test_invalid_range_shows_usage(self):
        output = self.run_rlist(["150"], self.area)
        self.assertIn("Usage: rlist [all] [low_vnum high_vnum]", output)
