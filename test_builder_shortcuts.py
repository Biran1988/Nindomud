import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import colors
import combat
import commands
import data_weapons
import olc
import world
from models import Player


class BuilderShortcutTests(unittest.TestCase):
    def setUp(self):
        self.session = NS(account=NS(staff_level="implementor"),
                          player=NS(name="Builder", room_vnum=9001), send=Mock())
        self.mob = combat.default_template(9002, "trainee")
        self.item = olc.default_object(9003, "training kunai")
        for target, value in [
            ("combat.MOB_TEMPLATES", {9002: self.mob}),
            ("combat.MOBS_BY_ROOM", {}),
            ("olc.OBJECT_TEMPLATES", {9003: self.item}),
            ("world.WORLD.rooms", {9001: world.Room(9001, "Academy", "Room")}),
            ("olc._log", Mock()),
        ]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def test_mob_short_names_keep_existing_template_keys(self):
        olc.cmd_mset(self.session, ["9002", "flags", "Wander"])
        olc.cmd_mset(self.session, ["9002", "hitdice", "2d6+4"])
        olc.cmd_mset(self.session, ["9002", "act_flags", "-Wander"])
        self.assertEqual(self.mob["hit_dice"], "2d6+4")
        self.assertNotIn("Wander", self.mob["act_flags"])
        olc.cmd_mset(self.session, ["9002", "flags", "Banker"])
        self.assertIn("Banker", self.mob["act_flags"])

    def test_item_short_names_flags_and_legacy_names(self):
        olc.cmd_oset(self.session, ["9003", "wear", "head"])
        olc.cmd_oset(self.session, ["9003", "wearloc", "head"])
        olc.cmd_oset(self.session, ["9003", "flags", "nosac"])
        olc.cmd_oset(self.session, ["9003", "concap", "8"])
        olc.cmd_oset(self.session, ["9003", "concap"])
        self.assertIn("concap", self.session.send.call_args.args[0])
        olc.cmd_oset(self.session, ["9003", "containercapacity", "9"])
        self.assertEqual(self.item["container_capacity"], 9)
        olc.cmd_oset(self.session, ["9003", "container_capacity", "8"])
        olc.cmd_oset(self.session, ["9003", "statbonus", "armorclass", "4"])
        self.assertIn("head", self.item["wear_flags"])
        self.assertEqual(self.item["wear_loc"], "head")
        self.assertEqual(self.item["extra_flags"], ["no_sac"])
        self.assertEqual(self.item["container_capacity"], 8)
        self.assertEqual(self.item["stat_bonuses"]["armor_class"], 4)
        olc.cmd_oset(self.session, ["9003", "extra_flags", "-nosac"])
        self.assertEqual(self.item["extra_flags"], [])
        olc.cmd_oset(self.session, ["9003", "wear_loc", "body"])
        self.assertEqual(self.item["wear_loc"], "body")
        olc.cmd_oset(self.session, ["fields"])
        shown = colors.render(self.session.send.call_args.args[0], False)
        self.assertIn("wearloc", shown)
        self.assertIn("wear", shown)
        self.assertIn("flags", shown)
        self.assertIn("concap", shown)
        self.assertNotIn("containercapacity", shown)
        self.assertNotIn("wear_flags", shown)
        self.assertTrue(all(len(line) <= 80 for line in shown.splitlines()))

    def test_weapon_type_sets_item_type_and_wear_slot(self):
        self.assertEqual(self.item["item_type"], "trash")
        olc.cmd_oset(self.session, ["9003", "weapontype", "kunai"])
        self.assertEqual((self.item["weapon_type"], self.item["item_type"],
                          self.item["wear_loc"]), ("kunai", "weapon", "wielded"))
        olc.cmd_ostat(self.session, ["9003"])
        shown = colors.render(self.session.send.call_args.args[0], False)
        self.assertIn("Item Type: Weapon", shown)
        self.assertIn("Weapon Type: Kunai", shown)
        self.assertIn("Damage:", shown)
        olc.cmd_oset(self.session, ["9003", "itemtype", "material"])
        self.assertEqual(self.item["item_type"], "weapon")
        olc.cmd_oset(self.session, ["9003", "wearloc", "body"])
        self.assertEqual(self.item["wear_loc"], "wielded")
        olc.cmd_oset(self.session, ["9003", "weapontype", "none"])
        olc.cmd_oset(self.session, ["9003", "itemtype", "material"])
        self.assertEqual((self.item["weapon_type"], self.item["item_type"]),
                         ("", "material"))
        self.assertEqual(self.item["wear_loc"], "")

    def test_direct_weapon_stats_set_combat_values_and_keep_old_aliases(self):
        olc.cmd_oset(self.session, ["9003", "weapontype", "kunai"])
        olc.cmd_oset(self.session, ["9003", "hitroll", "4"])
        olc.cmd_oset(self.session, ["9003", "damageroll", "7"])
        olc.cmd_oset(self.session, ["9003", "damage", "12"])
        self.assertEqual(self.item["stat_bonuses"], {"hitroll": 4, "damroll": 7})
        self.assertEqual(self.item["damage"], 12)
        player = NS(equipment={"wielded": "training kunai"})
        self.assertEqual(commands.equipped_weapon_hitroll_bonus(player), 4)
        self.assertEqual(commands.equipped_weapon_damroll_bonus(player), 7)
        self.assertEqual(commands.equipped_weapon_type_damage_bonus(player), 12)
        olc.cmd_ostat(self.session, ["9003"])
        shown = colors.render(self.session.send.call_args.args[0], False)
        self.assertIn("Hitroll: +4", shown)
        self.assertIn("Damageroll: +7", shown)
        self.assertIn("Damage: 12", shown)
        olc.cmd_oset(self.session, ["9003", "hit_roll", "5"])
        olc.cmd_oset(self.session, ["9003", "damage_roll", "8"])
        self.assertEqual(self.item["stat_bonuses"], {"hitroll": 5, "damroll": 8})
        olc.cmd_oset(self.session, ["9003", "statbonus", "damroll", "3"])
        self.assertEqual(self.item["stat_bonuses"]["damroll"], 3)
        olc.cmd_oset(self.session, ["9003", "damage", "-1"])
        self.assertEqual(self.item["damage"], 12)
        olc.cmd_oset(self.session, ["9003", "hitroll", "0"])
        self.assertNotIn("hitroll", self.item["stat_bonuses"])
        olc.cmd_oset(self.session, ["fields"])
        fields = colors.render(self.session.send.call_args.args[0], False)
        self.assertIn("hitroll", fields)
        self.assertIn("damageroll", fields)
        self.assertIn("damage", fields)
        self.assertTrue(all(len(line) <= 80 for line in fields.splitlines()))

    def test_set_damage_replaces_type_default_in_attacks_and_jutsu(self):
        olc.cmd_oset(self.session, ["9003", "weapontype", "sword"])
        player = Player("Student", "Student")
        player.equipment["wielded"] = "training kunai"
        with patch("combat.random.randint", return_value=5):
            before_attack = combat._player_attack_damage(player)
        before_jutsu = combat._jutsu_damage_bonus(player)
        olc.cmd_oset(self.session, ["9003", "damage", "14"])
        difference = 14 - 3  # sword's default base damage
        with patch("combat.random.randint", return_value=5):
            self.assertEqual(combat._player_attack_damage(player), before_attack + difference)
        self.assertEqual(combat._jutsu_damage_bonus(player), before_jutsu + difference)

    def test_room_flag_and_player_stat_joined_names(self):
        olc.cmd_rset(self.session, ["flags", "acceleratedhealing"])
        self.assertIn("accelerated_healing", world.WORLD.get(9001).flags)
        player = Player("Student", "Student")
        with patch.object(olc, "_find_target_player", return_value=(player, None)), \
             patch.object(olc.storage, "save_player"):
            olc.cmd_mset(self.session, ["Student", "maximumhealth", "123"])
            self.assertEqual(player.maximum_health, 123)
            olc.cmd_mset(self.session, ["Student", "maximum_health", "125"])
            self.assertEqual(player.maximum_health, 125)


class TrainShortcutsTests(unittest.TestCase):
    def test_short_and_full_names_use_same_costs_and_effects(self):
        player = NS(training_points=5, strength=10, constitution=10,
                    chakra_control=10, maximum_chakra=100)
        session = NS(player=player, send=Mock())
        for typed in ("str", "strength", "con", "cc"):
            commands.cmd_train(session, [typed])
        self.assertEqual((player.strength, player.constitution,
                          player.chakra_control, player.training_points), (12, 11, 11, 1))
        self.assertEqual(player.maximum_chakra, 110)
        commands.cmd_train(session, ["invalid"])
        self.assertEqual(player.training_points, 1)


class SayColorTests(unittest.TestCase):
    def test_say_uses_bright_green_for_speaker_and_room(self):
        session = NS(player=NS(name="Student", village="leaf", room_vnum=999999,
                               silenced_until=0), send=Mock(), broadcast_room=Mock())
        with patch("chat_moderation.record_and_check_spam", return_value=False):
            commands.cmd_say(session, ["Hello", "there"])
        session.send.assert_called_with("&gYou say, 'Hello there'&x")
        session.broadcast_room.assert_called_with(
            "&gStudent says, 'Hello there'&x", exclude_self=True)


class EquipmentSlotsTests(unittest.TestCase):
    def test_eq_shows_empty_slots_and_equipped_items(self):
        session = NS(player=NS(equipment={}), send=Mock())
        commands.cmd_equipment(session, [])
        empty_view = colors.render(session.send.call_args.args[0], False)
        self.assertIn("<head> (nothing)", empty_view)
        self.assertIn("<wielded> (nothing)", empty_view)
        self.assertIn("<tool> (nothing)", empty_view)
        self.assertLess(empty_view.index("<head>"), empty_view.index("<wielded>"))
        session.player.equipment["wielded"] = "Training Sword"
        commands.cmd_equipment(session, [])
        populated_view = colors.render(session.send.call_args.args[0], False)
        self.assertIn("<wielded> Training Sword", populated_view)
        self.assertIn("<head> (nothing)", populated_view)

    def test_wear_weapon_and_wear_all_use_wield_slot_and_learn_skill(self):
        weapon = olc.default_object(9004, "A Practice Kunai")
        builder = NS(account=NS(staff_level="implementor"),
                     player=NS(name="Builder"), send=Mock())
        player = NS(inventory=["A Practice Kunai"], equipment={},
                    learned_skills=[], skill_proficiencies={})
        session = NS(player=player, send=Mock())
        with patch.object(olc, "OBJECT_TEMPLATES", {9004: weapon}), \
             patch.object(olc, "_log"), \
             patch.object(commands, "_fire_item_trigger"):
            olc.cmd_oset(builder, ["9004", "weapontype", "kunai"])
            self.assertEqual(data_weapons.skill_for_item("A Practice Kunai"), "Kunai")
            commands.cmd_wear(session, ["kunai"])
            self.assertEqual(player.equipment["wielded"], "A Practice Kunai")
            self.assertNotIn("A Practice Kunai", player.inventory)
            self.assertEqual(player.learned_skills, ["Kunai"])
            player.inventory.append(player.equipment.pop("wielded"))
            player.learned_skills.clear()
            player.skill_proficiencies.clear()
            commands.cmd_wear(session, ["all"])
            self.assertEqual(player.equipment["wielded"], "A Practice Kunai")
            self.assertEqual(player.learned_skills, ["Kunai"])

    def test_exact_prototype_controls_skill_even_when_name_suggests_another_type(self):
        generic = olc.default_object(9004, "A Basic Kunai")
        generic.update(item_type="weapon", weapon_type="kunai", wear_loc="wielded")
        custom = olc.default_object(9005, "Kunai")
        builder = NS(account=NS(staff_level="implementor"),
                     player=NS(name="Builder"), send=Mock())
        player = NS(inventory=["Kunai"], equipment={},
                    learned_skills=[], skill_proficiencies={})
        session = NS(player=player, send=Mock())
        with patch.object(olc, "OBJECT_TEMPLATES", {9004: generic, 9005: custom}), \
             patch.object(olc, "_log"), \
             patch.object(commands, "_fire_item_trigger"):
            olc.cmd_oset(builder, ["9005", "weapontype", "sword"])
            self.assertEqual(data_weapons.skill_for_item("Kunai"), "Sword")
            commands.cmd_wear(session, ["Kunai"])
            self.assertEqual(player.equipment["wielded"], "Kunai")
            self.assertEqual(player.learned_skills, ["Sword"])


if __name__ == "__main__":
    unittest.main()
