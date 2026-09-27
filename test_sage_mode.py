"""Sage Mode must require a real configured elder and a long, saved progression."""
import unittest
import json
import os
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import config
import help_system
import olc
import sage_mode
import storage
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
        with patch("sage_mode.time.time", return_value=1000000 + 2 * sage_mode.TRAIN_INTERVAL), patch("sage_mode.random.randint", return_value=5):
            sage_mode.command(self.session, ["train"])
            self.assertEqual(self.player.sage_mastery["toad"], 2)
        self.assertEqual(Player.from_dict(self.player.to_dict()).sage_training_ready_at["toad"],
                         1000000 + 3 * sage_mode.TRAIN_INTERVAL)
        olc.cmd_mset(self.session, ["9002", "flags", "-SummonElder"])
        self.assertFalse(sage_mode.elder_families(self.player))
        sage_mode.command(self.session, ["train"])
        self.assertEqual(self.player.sage_mastery["toad"], 2)

    def test_existing_twelve_hour_wait_is_migrated_only_once(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(storage, "DATA_DIR", temp), \
                 patch.object(storage, "ACCOUNTS_DIR", os.path.join(temp, "accounts")), \
                 patch.object(storage, "PLAYERS_DIR", os.path.join(temp, "players")):
                storage.save_player(self.player)
                path = storage.player_path(self.player.name)
                with open(path, encoding="utf-8") as file:
                    old_save = json.load(file)
                old_save.pop("sage_training_interval_version")
                old_save["sage_training_ready_at"] = {"toad": 1000000 + 12 * 60 * 60}
                with open(path, "w", encoding="utf-8") as file:
                    json.dump(old_save, file)
                loaded = storage.load_player(self.player.name)
                self.assertEqual(loaded.sage_training_ready_at["toad"], 1000000 + 60 * 60)
                self.assertEqual(storage.load_player(self.player.name).sage_training_ready_at["toad"],
                                 loaded.sage_training_ready_at["toad"])
                with open(path, encoding="utf-8") as file:
                    self.assertEqual(json.load(file)["sage_training_interval_version"], 2)

    def test_summoning_and_five_family_toggle_and_upkeep(self):
        self.player.signed_summoning_contracts = list(sage_mode.data_summons.CONTRACTS)
        sage_mode.summon_command(self.session, ["toad"])
        self.assertEqual(combat.active_summon(self.player).summon_tier_key, "toad_3")
        sage_mode.summon_command(self.session, ["slug"])
        self.assertEqual(combat.active_summon(self.player).summon_tier_key, "slug_2")
        self.assertEqual(sum(1 for mobs in combat.MOBS_BY_ROOM.values() for mob in mobs if mob.summon_owner), 1)
        combat.dismiss_summon(self.player)
        self.player.sage_mastery = {key: 100 for key in sage_mode.data_summons.CONTRACTS}
        sage_mode.command(self.session, ["on", "slug"])
        self.assertEqual(self.player.chakra, 920)  # two summons; toggle has no upfront cost
        sage_mode.combat_pulse(self.session)
        self.assertEqual(self.player.chakra, 904)
        self.assertEqual(self.player.stamina, 92)
        self.assertEqual(self.player.health, 550)
        self.assertEqual(sage_mode.outgoing(self.player, 100), 120)
        self.assertEqual(sage_mode.incoming(self.player, 100), 90)
        sage_mode.command(self.session, [])  # bare command switches off
        self.assertFalse(sage_mode.active_contract(self.player))
        sage_mode.command(self.session, [])  # and restores the selected form
        self.assertEqual(sage_mode.active_contract(self.player), "slug")
        restored = Player.from_dict(self.player.to_dict())
        self.assertEqual(restored.sage_active_contract, "slug")
        self.assertEqual(restored.sage_preferred_contract, "slug")
        sage_mode.idle_upkeep(self.session)
        self.assertEqual(self.player.chakra, 892)
        sage_mode.command(self.session, ["off"])
        sage_mode.command(self.session, ["on", "toad"])
        self.assertEqual(sage_mode.accuracy(self.player), 15)
        self.player.chakra = 15
        sage_mode.idle_upkeep(self.session)
        self.assertEqual(self.player.chakra, 3)
        sage_mode.idle_upkeep(self.session)
        self.assertFalse(sage_mode.active_contract(self.player))
        self.assertEqual(self.player.chakra, 3)
        self.assertEqual(sage_mode.outgoing(self.player, 100), 100)
        self.assertEqual(self.player.sage_preferred_contract, "toad")

    def test_combat_toggle_can_start_mid_fight_and_turns_off_before_bonus_if_unfunded(self):
        self.player.signed_summoning_contracts = ["ninken"]
        self.player.sage_mastery = {"ninken": 100}
        self.session.combat_target = object()
        sage_mode.command(self.session, ["on", "ninken"])
        self.assertEqual(sage_mode.dodge(self.player), 10)
        self.player.stamina = 7
        sage_mode.combat_pulse(self.session)
        self.assertFalse(sage_mode.active_contract(self.player))
        self.assertEqual(self.player.stamina, 7)
        self.assertEqual(sage_mode.dodge(self.player), 0)
        self.session.combat_target = None
        self.player.stamina = 100
        sage_mode.command(self.session, [])
        self.assertEqual(sage_mode.active_contract(self.player), "ninken")

    def test_help_and_builder_field_reference(self):
        self.assertIn("SummonElder", olc.VALID_MOB_ACT_FLAGS)
        self.assertIn("summonfamily", olc._mset_field_reference())
        pages = {entry["primary_keyword"] for entry in help_system.DEFAULT_HELP_ENTRIES}
        self.assertTrue({"sage", "summon elder", "summon"} <= pages)
        self.assertIs(commands.COMMANDS["sage"], sage_mode.command)
        self.assertEqual(sage_mode.TRAIN_INTERVAL, 60 * 60)
        self.assertEqual(sage_mode.TRAIN_SUCCESS_PERCENT, 5)
        self.assertAlmostEqual((40 / 3) / config.REGEN_INTERVAL_SECONDS, 0.20)
        self.assertLess(config.IDLE_SHARINGAN_UPKEEP_INTERVAL_SECONDS, config.REGEN_INTERVAL_SECONDS)

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
        with patch("combat.random.randint", return_value=5):
            ordinary = combat._player_attack_damage(self.player)
            self.player.sage_active_contract = "monkey"
            empowered = combat._player_attack_damage(self.player)
        self.assertGreater(empowered, ordinary)
        self.assertEqual(sage_mode.outgoing(self.player, 100, weapon=True), 130)


if __name__ == "__main__":
    unittest.main()
