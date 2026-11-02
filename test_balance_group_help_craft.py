"""Regression coverage for the current help, forging, jutsu and group rules."""
import tempfile
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import data_crafting
import data_jutsu
import groups
import help_audit
import help_system
import jutsu_balance
import lumberjack
import network_bans
import olc
import storage
from models import Player


def actor(name, level=50, ip="198.51.100.1"):
    return NS(player=Player(name, name, level=level), connection_ip=ip,
              send=Mock(), request_close=Mock())


class GroupSecurityTests(unittest.TestCase):
    def test_twenty_level_span_and_same_ip(self):
        a = actor("A", 50, "198.51.100.9")
        b = actor("B", 70, "198.51.100.10")
        c = actor("C", 71, "198.51.100.11")
        same = actor("Same", 51, "::ffff:198.51.100.9")
        self.assertEqual(groups.group_join_violation(b, [a]), (None, None))
        self.assertIn("20", groups.group_join_violation(c, [a])[0])
        reason, ip = groups.group_join_violation(same, [a])
        self.assertIn("same IP", reason)
        self.assertEqual(ip, "198.51.100.9")
        self.assertTrue(groups.xp_eligible(a, b))
        self.assertFalse(groups.xp_eligible(a, c))
        self.assertFalse(groups.xp_eligible(a, same))

    def test_violation_calls_ban_and_disconnection(self):
        a = actor("A", 40, "203.0.113.7")
        b = actor("B", 41, "203.0.113.7")
        with patch.object(network_bans, "temporary_ip_ban") as ban:
            self.assertFalse(groups.enforce_join(b, [a]))
        ban.assert_called_once_with("203.0.113.7", duration_seconds=1800)
        b.request_close.assert_called_once()

    def test_persisted_ip_ban_expires_after_thirty_minutes(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(storage, "DATA_DIR", folder), \
             patch("session.ACTIVE_SESSIONS", []):
            with patch.object(network_bans.time, "time", return_value=100000.0):
                network_bans.temporary_ip_ban("203.0.113.99")
                self.assertTrue(network_bans.blocked("203.0.113.99", None))
                self.assertFalse(network_bans.blocked("203.0.113.100", None))
            with patch.object(network_bans.time, "time", return_value=101801.0):
                self.assertFalse(network_bans.blocked("203.0.113.99", None))



class JutsuBalanceTests(unittest.TestCase):
    def test_cost_increases_with_level_and_tier_but_copy_stays_exact(self):
        basic = data_jutsu.JUTSU["rasengan"]
        p = Player("Ninja", "Ninja", level=25, maximum_chakra=400)
        first = jutsu_balance.cast_cost(p, basic)
        p.level = 200
        p.maximum_chakra = 2400
        self.assertGreater(jutsu_balance.cast_cost(p, basic), first)
        self.assertGreater(jutsu_balance.cast_cost(p, data_jutsu.JUTSU["nanairo no rasengan"]),
                           jutsu_balance.cast_cost(p, basic))
        self.assertEqual(jutsu_balance.cast_cost(p, basic, base_override=130), 130)

    def test_each_attack_improves_and_pvp_hard_control_has_a_cap(self):
        jutsu = data_jutsu.JUTSU["chidori"]
        p = Player("Ninja", "Ninja", level=100)
        self.assertGreater(jutsu_balance.boosted_damage(p, jutsu, 100), 100)
        self.assertGreater(jutsu_balance.boosted_duration(p, jutsu, 3, effect="burning"), 3)
        self.assertLessEqual(jutsu_balance.boosted_duration(
            p, jutsu, 12, effect="paralyzed", is_pvp=True), 6)


class ForgingAndExamineTests(unittest.TestCase):
    def test_equipment_ingots_only_and_clean_enchantment_display(self):
        player = Player("Crafter", "Crafter", level=120, primary_class="bukijutsu")
        player.stamina = 500
        player.chakra = 1200
        player.inventory = ["A Chakra Steel Ingot", "A Chakra Steel Ingot"]
        output = []
        s = NS(player=player, send=output.append, is_busy=lambda: False,
               start_timed_action=lambda label, seconds, cb: cb(),
               enter_single_line=lambda prompt, cb: cb("chakra steel"))
        with patch("world_autosave.mark_dirty") as saved:
            commands.cmd_craft(s, ["weapon", "sword", "Storm", "Blade"])
        self.assertIn("Storm Blade", player.inventory)
        self.assertNotIn("A Chakra Steel Ingot", player.inventory)
        prototypes = [proto for proto in olc.OBJECT_TEMPLATES.values()
                      if proto.get("short_desc") == "Storm Blade"]
        self.assertTrue(prototypes)
        self.assertEqual(prototypes[-1]["craft_materials"],
                         ["chakra steel ingot", "chakra steel ingot"])
        self.assertEqual(prototypes[-1]["stat_bonuses"]["damroll"], 60)
        # This test removes only its temporary template; no player saves are touched.
        for vnum, proto in list(olc.OBJECT_TEMPLATES.items()):
            if proto.get("short_desc") == "Storm Blade":
                self.addCleanup(olc.OBJECT_TEMPLATES.pop, vnum, None)

    def test_examine_shows_enchant_not_rarity_and_trains_proficiency(self):
        from ninja_arts import base_item
        player = Player("Examiner", "Examiner", level=50)
        player.inventory = ["A Basic Kunai [art:sharp]"]
        player.learned_skills = ["Examine"]
        player.skill_proficiencies["Examine"] = 50
        output = []
        session = NS(player=player, send=output.append)
        with patch.object(combat.random, "randint", return_value=1):
            commands.cmd_examine(session, ["kunai"])
        report = "\n".join(output)
        self.assertIn("Sharp", report)
        self.assertNotIn("Rarity:", report)
        self.assertNotIn("[art:sharp]", report)
        self.assertEqual(base_item(player.inventory[0]), "A Basic Kunai")
        self.assertGreater(player.skill_proficiencies["Examine"], 50)

    def test_steel_axe_reduces_scraps_and_elder_oak_is_level_sixty(self):
        find = {name: (level, weight) for name, level, weight, _ in lumberjack.FIND_TABLE}
        self.assertEqual(find["an elder oak log"][0], 60)
        for tier in (2, 3):
            table = {name: weight for name, _, weight, _ in lumberjack.weighted_find_table(tier)}
            self.assertLess(table["a bundle of kindling"], find["a bundle of kindling"][1])
            self.assertLess(table["a birch branch"], find["a birch branch"][1])


class HelpCoverageTests(unittest.TestCase):
    def test_all_registered_public_commands_have_a_topic(self):
        pages = {e["primary_keyword"].casefold() for e in help_system.DEFAULT_HELP_ENTRIES}
        for command in commands.COMMANDS:
            if command not in help_audit.SECRET_KEYS:
                self.assertIn(command, pages)
        aliases = {alias.casefold() for entry in help_system.DEFAULT_HELP_ENTRIES
                   for alias in entry.get("keywords", ())}
        for art_key, art in data_jutsu.JUTSU.items():
            if not art.get("secret") and art_key not in help_audit.SECRET_KEYS:
                self.assertIn(art_key, pages | aliases)

    def test_help_examine_and_craft_follow_latest_rules(self):
        by_key = {e["primary_keyword"]: e["body"] for e in help_system.DEFAULT_HELP_ENTRIES}
        self.assertIn("rarity is never shown", by_key["examine"].lower())
        self.assertIn("no wood", by_key["craft"].lower())
        self.assertIn("30 minutes", by_key["group"].lower())


if __name__ == "__main__":
    unittest.main()
