"""Sage Mode must require a real configured elder and a long, saved progression."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import help_system
import olc
import sage_mode
import world
from models import Player


class SageModeTests(unittest.TestCase):
    def setUp(self):
        self.player = Player(name="Student", account_name="Student", level=80, room_vnum=9001,
                             chakra=1000, maximum_chakra=1000)
        self.player.maximum_health = 1000
        self.player.health = 500
        self.session = NS(player=self.player, account=NS(staff_level="implementor"),
                          combat_target=None, pvp_target=None, send=Mock())
        self.template = combat.default_template(9002, "the toad elder")
        for target, value in [("combat.MOB_TEMPLATES", {9002: self.template}),
                              ("combat.MOBS_BY_ROOM", {}),
                              ("world.WORLD.rooms", {9001: world.Room(9001, "Sanctuary", "Elder's cave")}),
                              ("olc._log", Mock())]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def test_builder_flag_and_family_gate_contract_and_training(self):
        sage_mode.sign_command(self.session)
        self.assertFalse(self.player.signed_summoning_contracts)
        olc.cmd_mset(self.session, ["9002", "flags", "SummonElder"])
        olc.cmd_mset(self.session, ["9002", "summonfamily", "toad"])
        self.assertEqual(self.template["summon_family"], "toad")
        mob = combat.spawn_mob(9002, 9001)
        self.assertTrue(combat.is_immortal_mob(mob))
        self.assertEqual(sage_mode.elder_families(self.player), {"toad"})
        sage_mode.sign_command(self.session)
        self.assertEqual(self.player.signed_summoning_contracts, ["toad"])
        with patch("sage_mode.time.time", return_value=1000000), patch("sage_mode.random.randint", return_value=1):
            sage_mode.command(self.session, ["train"])
            self.assertEqual(self.player.sage_mastery["toad"], 1)
            sage_mode.command(self.session, ["train"])
            self.assertEqual(self.player.sage_mastery["toad"], 1)
        with patch("sage_mode.time.time", return_value=1000000 + sage_mode.TRAIN_INTERVAL), patch("sage_mode.random.randint", return_value=100):
            sage_mode.command(self.session, ["train"])
            self.assertEqual(self.player.sage_mastery["toad"], 1)
        self.assertEqual(Player.from_dict(self.player.to_dict()).sage_training_ready_at["toad"],
                         1000000 + 2 * sage_mode.TRAIN_INTERVAL)
        olc.cmd_mset(self.session, ["9002", "flags", "-SummonElder"])
        self.assertFalse(sage_mode.elder_families(self.player))
        sage_mode.command(self.session, ["train"])
        self.assertEqual(self.player.sage_mastery["toad"], 1)

    def test_summoning_and_five_family_mastery_and_expiration(self):
        self.player.signed_summoning_contracts = list(sage_mode.data_summons.CONTRACTS)
        sage_mode.summon_command(self.session, ["toad"])
        self.assertEqual(combat.active_summon(self.player).summon_tier_key, "toad_3")
        sage_mode.summon_command(self.session, ["slug"])
        self.assertEqual(combat.active_summon(self.player).summon_tier_key, "slug_2")
        self.assertEqual(sum(1 for mobs in combat.MOBS_BY_ROOM.values() for mob in mobs if mob.summon_owner), 1)
        combat.dismiss_summon(self.player)
        self.player.sage_mastery = {key: 100 for key in sage_mode.data_summons.CONTRACTS}
        with patch("sage_mode.time.time", return_value=1000000):
            sage_mode.command(self.session, ["activate", "slug"])
            self.assertEqual(self.player.chakra, 820)  # two summons plus activation
            sage_mode.combat_pulse(self.session)
            self.assertEqual(self.player.health, 550)
            self.assertEqual(sage_mode.outgoing(self.player, 100), 120)
            self.assertEqual(sage_mode.incoming(self.player, 100), 90)
            sage_mode.command(self.session, ["off"])
            sage_mode.command(self.session, ["activate", "toad"])
            self.assertFalse(sage_mode.active_contract(self.player))
        self.assertIn("not recovered", self.session.send.call_args.args[0])
        with patch("sage_mode.time.time", return_value=1000000 + sage_mode.COOLDOWN):
            sage_mode.command(self.session, ["activate", "toad"])
            self.assertEqual(sage_mode.accuracy(self.player), 15)
        with patch("sage_mode.time.time", return_value=1000000 + sage_mode.COOLDOWN + sage_mode.DURATION + 1):
            self.assertFalse(sage_mode.active_contract(self.player))
            self.assertEqual(sage_mode.outgoing(self.player, 100), 100)

    def test_help_and_builder_field_reference(self):
        self.assertIn("SummonElder", olc.VALID_MOB_ACT_FLAGS)
        self.assertIn("summonfamily", olc._mset_field_reference())
        pages = {entry["primary_keyword"] for entry in help_system.DEFAULT_HELP_ENTRIES}
        self.assertTrue({"sage", "summon elder", "summon"} <= pages)
        self.assertIs(commands.COMMANDS["sage"], sage_mode.command)

    def test_family_assignment_is_live_and_real_attack_uses_mode(self):
        olc.cmd_mset(self.session, ["9002", "flags", "SummonElder"])
        mob = combat.spawn_mob(9002, 9001)
        self.assertFalse(sage_mode.elder_families(self.player))  # flag alone is insufficient
        for family in sage_mode.data_summons.CONTRACTS:
            olc.cmd_mset(self.session, ["9002", "summonfamily", family])
            self.assertEqual(sage_mode.elder_families(self.player), {family})
        self.assertTrue(combat.is_immortal_mob(mob))
        self.player.signed_summoning_contracts = ["monkey"]
        self.player.sage_mastery = {"monkey": 100}
        self.player.equipment["wielded"] = "A Basic Ninja Sword"
        with patch("combat.random.randint", return_value=5), patch("sage_mode.time.time", return_value=1000):
            ordinary = combat._player_attack_damage(self.player)
            self.player.sage_active_contract = "monkey"
            self.player.sage_ends_at = 2000
            empowered = combat._player_attack_damage(self.player)
        self.assertGreater(empowered, ordinary)
        self.assertEqual(sage_mode.outgoing(self.player, 100, weapon=True), 100)  # real time expired


if __name__ == "__main__":
    unittest.main()
