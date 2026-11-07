"""Looking at a player or mob shows equipped armor, weapons and accessories."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import combat
import commands
import session
import world
from models import Player


class LookEquipmentTests(unittest.TestCase):
    def setUp(self):
        self.room = world.Room(999312, "Practice Courtyard", "A peaceful court.")
        room_patch = patch.object(world.WORLD, "rooms", {self.room.vnum: self.room})
        room_patch.start()
        self.addCleanup(room_patch.stop)
        self.viewer_output = []
        self.target_output = []
        self.viewer = self.make_session("Observer", self.viewer_output)
        self.target = self.make_session("Sakura", self.target_output)
        self.target.player.description = "A wandering swordswoman."
        self.target.player.equipment = {
            "body": "A Reinforced Ninja Shirt",
            "head": "A Hidden Leaf Headband",
            "wielded": "A Chakra Steel Katana",
            "offhand": "An Iron Kunai",
            "back": "A Shinobi Cloak",
            "tool": "A Copper Hoe",
            "finger": "A Jade Ring",
        }
        self.target.player.inventory.append("A Private Secret Scroll")
        self.viewer_output.clear()

    def make_session(self, name, output):
        active = session.Session(output.append, lambda: None)
        active.state = session.State.PLAYING
        active.account = NS(name=name, staff_level="player")
        active.player = Player(name, name, village="leaf",
                               room_vnum=self.room.vnum, primary_class="bukijutsu")
        self.addCleanup(lambda s=active: session.ACTIVE_SESSIONS.remove(s)
                        if s in session.ACTIVE_SESSIONS else None)
        return active

    def look_text(self, args):
        self.viewer_output.clear()
        commands.cmd_look(self.viewer, args)
        return "\n".join(self.viewer_output)

    def test_player_look_shows_worn_armor_accessories_and_both_weapons(self):
        message = self.look_text(["Sakura"])
        self.assertIn("A wandering swordswoman.", message)
        self.assertIn("Equipment:", message)
        self.assertIn("Hidden Leaf Headband", message)
        self.assertIn("Reinforced Ninja Shirt", message)
        self.assertIn("Shinobi Cloak", message)
        self.assertIn("Jade Ring", message)
        self.assertIn("Wielded weapon", message)
        self.assertIn("Chakra Steel Katana", message)
        self.assertIn("Off-hand weapon", message)
        self.assertIn("Iron Kunai", message)
        self.assertIn("Held tool", message)
        self.assertIn("Copper Hoe", message)
        self.assertLess(message.index("Hidden Leaf Headband"), message.index("Chakra Steel Katana"))
        self.assertLess(message.index("Chakra Steel Katana"), message.index("Iron Kunai"))
        self.assertNotIn("Private Secret Scroll", message)

    def test_self_look_also_shows_equipped_items(self):
        self.viewer.player.equipment["wielded"] = "A Silver Katana"
        text = self.look_text(["self"])
        self.assertIn("Silver Katana", text)
        self.assertIn("Wielded weapon", text)
        self.assertIn("Equipment:", text)

    def test_empty_equipment_is_clearly_reported(self):
        text = self.look_text(["self"])
        self.assertIn("nothing equipped", text)
        self.assertNotIn("Chakra Steel Katana", text)

    def test_hiding_player_still_prevents_looking_at_equipment(self):
        self.target.player.invisible = True
        text = self.look_text(["Sakura"])
        self.assertNotIn("Chakra Steel Katana", text)
        self.assertNotIn("A wandering swordswoman", text)
        self.assertIn("don't see", text)

    def test_clone_original_body_uses_original_equipment(self):
        self.viewer._clone_original_player = self.target.player
        text = self.look_text(["Sakura"])
        self.assertIn("Chakra Steel Katana", text)
        self.assertIn("A wandering swordswoman", text)

    def test_mob_with_equipment_shows_worn_and_wielded_gear(self):
        enemy = NS(
            name="a wandering samurai", template_vnum=9911,
            active_status_effects={},
            equipment={"body": "An Iron Cuirass", "wielded": "A Long Katana"},
        )
        with patch.object(combat, "find_mob", return_value=enemy), \
             patch.dict(combat.MOB_TEMPLATES,
                        {9911: {"description": "A guarded mercenary.", "act_flags": []}}):
            text = self.look_text(["wandering", "samurai"])
        self.assertIn("A guarded mercenary.", text)
        self.assertIn("Iron Cuirass", text)
        self.assertIn("Long Katana", text)

    def test_unknown_custom_equipment_slot_is_displayed(self):
        self.target.player.equipment["left_shoulder"] = "An Ancient Paudron"
        text = self.look_text(["Sakura"])
        self.assertIn("Left Shoulder", text)
        self.assertIn("Ancient Paudron", text)


if __name__ == "__main__":
    unittest.main()
