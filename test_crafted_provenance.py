"""No same-IP alt can obtain a stamped forged item via supported exchanges."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import commands
import crafted_provenance as provenance
import models
import olc
import trade
import world


class ForgedItemAltGuardTests(unittest.TestCase):
    def setUp(self):
        self.name = "An IP-Bound Test Blade"
        self.vnum = 877789
        self.proto = dict(olc.DEFAULT_OBJECT_FIELDS)
        self.proto.update(short_desc=self.name, item_type="weapon",
                          wear_loc="wielded", weapon_type="sword",
                          craft_materials=["iron ingot", "iron ingot"],
                          stat_bonuses={"hitroll": 10, "damroll": 10})
        olc.OBJECT_TEMPLATES[self.vnum] = self.proto
        self.addCleanup(olc.OBJECT_TEMPLATES.pop, self.vnum, None)
        self.creator = self.session("Maker", "192.0.2.20")
        provenance.stamp(self.proto, self.creator)
        self.alt = self.session("Alt", "192.0.2.20")
        self.friend = self.session("Friend", "198.51.100.6")

    def session(self, name, ip):
        player = models.Player(name, name)
        player.room_vnum = 99881
        player.last_connection_ip = ip
        sent = []
        return NS(player=player, connection_ip=ip, send=sent.append,
                  messages=sent, account=NS(staff_level="player"),
                  active_sessions=lambda: [], trade=None)

    def test_hidden_creator_stamp_preserves_original_item_stats_and_name(self):
        self.assertEqual(self.proto["short_desc"], self.name)
        self.assertEqual(self.proto["stat_bonuses"], {"hitroll": 10, "damroll": 10})
        self.assertEqual(self.proto["crafted_by_character"], "Maker")
        self.assertEqual(self.proto["crafted_by_ip"], "192.0.2.20")
        self.assertFalse(provenance.denied(self.name, self.creator.player, session=self.creator))
        self.assertTrue(provenance.denied(self.name, self.alt.player, session=self.alt))
        self.assertFalse(provenance.denied(self.name, self.friend.player, session=self.friend))
        self.assertFalse(provenance.denied("A Random Uncrafted Sword", self.alt.player, session=self.alt))
        self.assertTrue(provenance.denied(self.name, self.session("Unknown", None).player,
                                          session=self.session("Unknown", None)))

    def test_examine_never_leaks_crafter_character_or_ip(self):
        self.friend.player.inventory.append(self.name)
        self.friend.player.learned_skills.append("Examine")
        self.friend.player.skill_proficiencies["Examine"] = 90
        with (patch("skill_training.needs_first_practice", return_value=False),
              patch("combat.grow_skill_from_usage")):
            commands.cmd_examine(self.friend, ["blade"])
        text = "\\n".join(self.friend.messages)
        self.assertIn("Hitroll: +10", text)
        self.assertNotIn("192.0.2.20", text)
        self.assertNotIn("crafted_by_ip", text)
        self.assertNotIn("Maker", text)

    def test_ipv4_mapped_v6_is_same_origin(self):
        alt_mapped = self.session("AltMapped", "::ffff:192.0.2.20")
        self.assertTrue(provenance.denied(self.name, alt_mapped.player, session=alt_mapped))

    def test_alt_cannot_get_from_ground_even_with_get_all(self):
        room = world.Room(99881, "Test Ground", "Room.")
        room.ground_items = [self.name]
        with patch.object(commands.WORLD, "get", return_value=room):
            commands.cmd_get(self.alt, ["blade"])
            self.assertEqual(room.ground_items, [self.name])
            self.assertNotIn(self.name, self.alt.player.inventory)
            commands.cmd_get(self.alt, ["all"])
            self.assertEqual(room.ground_items, [self.name])
            self.assertNotIn(self.name, self.alt.player.inventory)
            commands.cmd_get(self.friend, ["blade"])
        self.assertIn(self.name, self.friend.player.inventory)

    def test_direct_gift_blocks_creator_to_alt_and_alt_to_friend(self):
        self.creator.player.inventory = [self.name]
        self.creator.active_sessions = lambda: [self.creator, self.alt]
        commands.cmd_give(self.creator, ["blade", "Alt"])
        self.assertEqual(self.creator.player.inventory, [self.name])
        self.assertEqual(self.alt.player.inventory, [])
        self.alt.player.inventory = [self.name]
        self.alt.active_sessions = lambda: [self.alt, self.friend]
        commands.cmd_give(self.alt, ["blade", "Friend"])
        self.assertEqual(self.alt.player.inventory, [self.name])
        self.assertEqual(self.friend.player.inventory, [])
        self.creator.active_sessions = lambda: [self.creator, self.friend]
        commands.cmd_give(self.creator, ["blade", "Friend"])
        self.assertIn(self.name, self.friend.player.inventory)

    def test_trade_is_atomic_when_alt_restricted(self):
        self.creator.player.inventory = [self.name]
        self.alt.player.inventory = ["A Plain Stick"]
        t = trade.start_trade(self.creator, self.alt)
        t.accepted = t.confirmed_a = t.confirmed_b = True
        t.offer_a["items"].append(self.name)
        t.offer_b["items"].append("A Plain Stick")
        before_a = list(self.creator.player.inventory)
        before_b = list(self.alt.player.inventory)
        with self.assertRaises(ValueError):
            trade.complete_trade(t)
        self.assertEqual(before_a, self.creator.player.inventory)
        self.assertEqual(before_b, self.alt.player.inventory)

    def test_corpse_loot_and_autoloot_skip_alt_locked_gear(self):
        import corpses
        corpse = corpses.Corpse("the corpse of Test", 99881,
                                items=[self.name, "A Plain Stick"])
        found = corpses.loot_gear(self.alt.player, corpse, session=self.alt)
        self.assertEqual(found, ["A Plain Stick"])
        self.assertEqual(corpse.items, [self.name])
        found = corpses.loot_gear(self.friend.player, corpse, session=self.friend)
        self.assertEqual(found, [self.name])
        self.assertEqual(corpse.items, [])

    def test_offline_last_known_ip_is_used_for_auction_recipients(self):
        self.assertTrue(provenance.denied(self.name, self.alt.player))
        self.assertFalse(provenance.denied(self.name, self.friend.player))


if __name__ == "__main__":
    unittest.main()
