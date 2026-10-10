"""Gameplay, event boundaries, transaction safety, and save compatibility."""

from datetime import date
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

import combat
import commands
import inventory
import lightsabers as sabers
from models import Player
import olc
import seasonal_events as events
import storage
import world_persistence
import data_weapons
import help_system


class Session:
    def __init__(self, name="SaberTester"):
        self.player = Player(name, name)
        self.messages = []
        self.combat_target = self.pvp_target = None
        self.account = None

    def send(self, message):
        self.messages.append(message)

    def broadcast_room(self, message, exclude_self=False):
        self.messages.append(message)


class LightsaberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for field, value in (("DATA_DIR", self.temp.name),
                             ("ACCOUNTS_DIR", str(Path(self.temp.name) / "accounts")),
                             ("PLAYERS_DIR", str(Path(self.temp.name) / "players"))):
            p = patch.object(storage, field, value)
            p.start()
            self.addCleanup(p.stop)
        sabers.register_items()
        self.session = Session()

    def test_event_boundaries_and_timezone(self):
        self.assertEqual(str(events.EVENT_ZONE), "America/Detroit")
        for year in (2026, 2027, 2028):
            self.assertFalse(events.may_fourth_active(date(year, 5, 3)))
            self.assertTrue(events.may_fourth_active(date(year, 5, 4)))
            self.assertFalse(events.may_fourth_active(date(year, 5, 5)))

    def test_visitor_is_temporary_and_gifts_persist_per_year(self):
        with patch.object(combat, "MOBS_BY_ROOM", {}), patch.object(combat, "MOB_TEMPLATES", {}):
            day = date(2027, 5, 4)
            events.sync_visitors(day)
            events.sync_visitors(day)
            for room in events.kage_rooms():
                visitors = [m for m in combat.mobs_in_room(room) if m.template_vnum == events.JEDI_VNUM]
                self.assertEqual(len(visitors), 1)
                self.assertTrue(combat.is_immortal_mob(visitors[0]))
            self.assertNotIn(str(events.JEDI_VNUM), world_persistence.snapshot_world()["mobs"])
            self.session.player.room_vnum = events.hokage_room()
            with patch.object(events, "local_date", return_value=day):
                commands.cmd_ask(self.session, ["jedi", "about", "lightsaber"])
            loaded = storage.load_player(self.session.player.name)
            self.assertEqual(loaded.last_may_fourth_gift_year, 2027)
            self.session.player = loaded
            events.claim_may_fourth(self.session, day)
            self.assertEqual(loaded.inventory, [sabers.item_name()])
            events.sync_visitors(date(2027, 5, 5))
            self.assertNotIn(events.JEDI_VNUM, combat.MOB_TEMPLATES)
            self.assertFalse(any(m.template_vnum == events.JEDI_VNUM
                                 for mobs in combat.MOBS_BY_ROOM.values() for m in mobs))
            self.assertFalse(events.claim_may_fourth(self.session, date(2027, 5, 5)))
            events.sync_visitors(date(2028, 5, 4))
            self.assertTrue(events.claim_may_fourth(self.session, date(2028, 5, 4)))
            self.assertEqual(len(loaded.inventory), 2)

    def test_full_inventory_does_not_consume_annual_claim(self):
        with patch.object(combat, "MOBS_BY_ROOM", {}), patch.object(combat, "MOB_TEMPLATES", {}):
            day = date(2027, 5, 4)
            events.sync_jedi(day)
            self.session.player.room_vnum = events.hokage_room()
            self.session.player.inventory = [f"item{i}" for i in range(inventory.MAX_INVENTORY_SLOTS)]
            self.assertTrue(events.claim_may_fourth(self.session, day))
            self.assertEqual(self.session.player.last_may_fourth_gift_year, 0)
            self.session.player.inventory.pop()
            self.assertTrue(events.claim_may_fourth(self.session, day))
            self.assertEqual(self.session.player.last_may_fourth_gift_year, 2027)

    def test_ignition_changes_real_combat_bonuses_and_sword_skill(self):
        p = self.session.player
        p.inventory = [sabers.item_name()]
        commands.cmd_wield(self.session, ["lightsaber"])
        self.assertEqual(commands.equipped_weapon_type_damage_bonus(p), 0)
        self.assertNotEqual(data_weapons.weapon_type_for_item(p.equipment["wielded"]), "sword")
        with patch.object(combat.random, "randint", return_value=5):
            before = combat._player_attack_damage(p)
            commands.COMMANDS["activate"](self.session, ["lightsaber"])
            after = combat._player_attack_damage(p)
        self.assertEqual(after - before, sabers.BLADE_DAMAGE)
        self.assertEqual(commands.equipped_weapon_hitroll_bonus(p), 2)
        self.assertEqual(data_weapons.weapon_type_for_item(p.equipment["wielded"]), "sword")
        self.assertEqual(data_weapons.attack_verb_for_item(p.equipment["wielded"]), "slash")
        self.assertIn("Sword", p.learned_skills)
        commands.COMMANDS["deactivate"](self.session, ["lightsaber"])
        self.assertEqual(commands.equipped_weapon_type_damage_bonus(p), 0)
        self.assertEqual(commands.equipped_weapon_hitroll_bonus(p), 0)

    def test_all_existing_cut_gems_change_only_selected_saber(self):
        for gem, color in sabers.GEM_COLORS.items():
            with self.subTest(gem=gem):
                p = self.session.player
                p.inventory = [sabers.item_name(), sabers.item_name(), gem.title()]
                commands.COMMANDS["insert"](self.session, gem.split() + ["into", "2.lightsaber"])
                self.assertEqual(p.inventory, [sabers.item_name(), sabers.item_name(color)])
                commands.COMMANDS["activate"](self.session, ["2.lightsaber"])
                self.assertEqual(p.inventory[0], sabers.item_name())
                self.assertEqual(sabers.state(p.inventory[1]), (color, True))
                loaded = storage.load_player(p.name)
                self.assertEqual(loaded.inventory, p.inventory)

    def test_equipped_color_and_state_survive_reload_and_art_suffix(self):
        p = self.session.player
        p.equipment["wielded"] = sabers.item_name() + " [art:sharp]"
        p.inventory = ["A Cut Ruby"]
        sabers.insert_gem(self.session, ["cut", "ruby"])
        sabers.activate(self.session, [])
        loaded = storage.load_player(p.name)
        self.assertEqual(loaded.equipment["wielded"], sabers.item_name("red", True) + " [art:sharp]")
        self.assertEqual(commands.equipped_weapon_type_damage_bonus(loaded), sabers.BLADE_DAMAGE)
        self.assertIn("&[196]", commands.rarity_colored_name(loaded.equipment["wielded"]))
        self.assertFalse(loaded.inventory)

    def test_invalid_gems_active_blades_and_combat_do_not_consume_items(self):
        p = self.session.player
        p.inventory = [sabers.item_name(), "A Raw Ruby", "A Cut Ruby"]
        original = list(p.inventory)
        sabers.insert_gem(self.session, ["raw", "ruby"])
        self.assertEqual(p.inventory, original)
        self.session.pvp_target = object()
        sabers.insert_gem(self.session, ["cut", "ruby"])
        self.assertEqual(p.inventory, original)
        self.session.pvp_target = None
        sabers.activate(self.session, [])
        active_inventory = list(p.inventory)
        sabers.insert_gem(self.session, ["cut", "ruby"])
        self.assertEqual(p.inventory, active_inventory)

    def test_recolor_stack_limit_rolls_back_gem_and_weapon(self):
        p = self.session.player
        p.inventory = [sabers.item_name()] + [sabers.item_name("red")] * inventory.MAX_STACK_SIZE + ["A Cut Ruby"]
        original = list(p.inventory)
        sabers.insert_gem(self.session, ["cut", "ruby"])
        self.assertEqual(p.inventory, original)

    def test_use_toggles_after_event_and_missing_indices_do_not_change_other_items(self):
        p = self.session.player
        p.inventory = [sabers.item_name()]
        with patch.object(events, "local_date", return_value=date(2027, 6, 1)):
            commands.cmd_use(self.session, ["lightsaber"])
        self.assertEqual(sabers.state(p.inventory[0]), ("green", True))
        sabers.deactivate(self.session, ["2.lightsaber"])
        self.assertTrue(sabers.state(p.inventory[0])[1])
        commands.cmd_use(self.session, ["lightsaber"])
        self.assertFalse(sabers.state(p.inventory[0])[1])

    def test_hidden_command_listing_and_existing_save_defaults(self):
        self.assertEqual(Player.from_dict(self.session.player.to_dict()).last_may_fourth_gift_year, 0)
        with patch.object(events, "local_date", return_value=date(2027, 5, 3)):
            commands.cmd_commands(self.session, [])
            self.assertNotIn("lightsaber", self.session.messages[-1])
            self.session.player.inventory = [sabers.item_name()]
            commands.cmd_commands(self.session, [])
            self.assertIn("lightsaber", self.session.messages[-1])

    def test_help_is_hidden_until_event_or_ownership(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(help_system, "HELP_DIR", tmp), \
                patch.object(events, "local_date", return_value=date(2027, 5, 3)):
            help_system.seed_default_help()
            help_system.cmd_help(self.session, [])
            self.assertNotIn("lightsaber", self.session.messages[-1])
            help_system.cmd_help(self.session, ["activate"])
            self.assertIn("doesn't exist", self.session.messages[-1])
            self.session.player.inventory = [sabers.item_name()]
            help_system.cmd_help(self.session, ["insert"])
            self.assertIn("Inserting consumes one cut gem", self.session.messages[-1])


if __name__ == "__main__":
    unittest.main()
