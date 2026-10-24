"""General skill unlocks, real world visibility/movement and Genjutsu defense."""
from types import SimpleNamespace as NS
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import combat
import commands
import data_jutsu
import general_skills as skills
import genjutsu
import hidden_mist
import leveling
import mob_aggression
import skill_training
import status_effects
import tracking
import world
import weather
import sage_mode
from models import Player
from session import ACTIVE_SESSIONS, Session, State


class GeneralSkillTests(unittest.TestCase):
    def setUp(self):
        self.room = world.Room(992710, "Stealth Clearing", "A quiet clearing.")
        self.next_room = world.Room(992711, "Stealth Path", "A narrow path.")
        self.room.exits["north"] = self.next_room.vnum
        self.next_room.exits["south"] = self.room.vnum
        for room in (self.room, self.next_room):
            world.WORLD.rooms[room.vnum] = room
            self.addCleanup(world.WORLD.rooms.pop, room.vnum, None)
        self.actor, self.output = self.make_session("StealthNinja")
        self.viewer, self.view_output = self.make_session("Observer")
        self.growth = patch.object(combat, "grow_skill_from_usage")
        self.grow = self.growth.start()
        self.addCleanup(self.growth.stop)

    def make_session(self, name, level=50):
        output = []
        session = Session(output.append, lambda: None)
        session.state = State.PLAYING
        session.account = NS(name=name, staff_level="player")
        session.player = Player(name, name, primary_class="taijutsu", level=level,
                                room_vnum=self.room.vnum)
        player = session.player
        player.chakra = player.stamina = 1000
        player.health = player.maximum_health = 1000
        player.practice_gate_enabled = True
        with patch.object(leveling.storage, "save_player"):
            leveling.sync_universal_skills(player)
        for key in data_jutsu.GENERAL_UTILITY_SKILLS:
            name = data_jutsu.JUTSU[key]["display_name"]
            if name in player.learned_skills:
                player.skill_proficiencies[name] = 50
                skill_training.mark_practiced(player, name)
        skill_training.mark_practiced(player, "Scan")
        self.addCleanup(lambda: ACTIVE_SESSIONS.remove(session) if session in ACTIVE_SESSIONS else None)
        output.clear()
        return session, output

    def cast(self, session, command):
        commands.dispatch_line(session, command)

    def test_unlock_levels_all_classes_and_returning_player_sync(self):
        for cls in ("taijutsu", "ninjutsu", "genjutsu", "bukijutsu"):
            for key, (_, level, _, _) in data_jutsu.GENERAL_UTILITY_SKILLS.items():
                self.assertNotIn(key, data_jutsu.all_unlocked_for_class(cls, level - 1))
                self.assertIn(key, data_jutsu.jutsu_for_class_at_level(cls, level))
            player = Player("Returning", "Returning", primary_class=cls, level=50)
            leveling.sync_universal_skills(player)
            for name, _, _, _ in data_jutsu.GENERAL_UTILITY_SKILLS.values():
                self.assertIn(name, player.learned_skills)
                self.assertEqual(player.skill_proficiencies[name], 0)

    def test_bare_and_perform_commands_cost_duration_cooldown_and_off(self):
        for key, effect in skills.EFFECT_KEYS.items():
            info = data_jutsu.JUTSU[key]
            before = self.actor.player.chakra, self.actor.player.stamina
            self.cast(self.actor, key)
            self.assertTrue(skills.active(self.actor.player, effect), key)
            self.assertEqual(self.actor.player.active_status_effects[effect]["duration"],
                             1 if status_effects.EFFECT_DEFS[effect].get("toggled") else 110)
            self.assertEqual(before[0] - self.actor.player.chakra, info["chakra_cost"])
            self.assertEqual(before[1] - self.actor.player.stamina, info["stamina_cost"])
            growth_calls = self.grow.call_count
            self.cast(self.actor, key + " on")
            self.assertEqual(self.grow.call_count, growth_calls)
            self.cast(self.actor, key + " off")
            self.assertFalse(skills.active(self.actor.player, effect))
            self.cast(self.actor, "perform " + key)
            self.assertFalse(skills.active(self.actor.player, effect))  # cooldown retained
            self.actor.player.cooldowns[key] = 0
            self.cast(self.actor, "perform " + key)
            self.assertTrue(skills.active(self.actor.player, effect))
            self.cast(self.actor, key + " off")

    def test_first_practice_and_unknown_skills_cannot_activate(self):
        for key, effect in skills.EFFECT_KEYS.items():
            name = data_jutsu.JUTSU[key]["display_name"]
            self.actor.player.practiced_skills.remove(name)
            self.cast(self.actor, key)
            self.assertFalse(skills.active(self.actor.player, effect))
            self.actor.player.learned_skills.remove(name)
            self.cast(self.actor, key)
            self.assertFalse(skills.active(self.actor.player, effect))

    def test_immortal_auto_mastery_works_without_teacher_lessons(self):
        player = self.actor.player
        self.actor.account.staff_level = "helper"
        player._immortal_skill_mastery = True
        player.practiced_skills.clear()
        leveling.grant_immortal_jutsu(player)
        for key, effect in skills.EFFECT_KEYS.items():
            with self.subTest(skill=key):
                self.assertEqual(player.skill_proficiencies[data_jutsu.JUTSU[key]["display_name"]], 100)
                self.cast(self.actor, key)
                self.assertTrue(skills.active(player, effect), self.output)
                self.assertEqual(player.active_status_effects[effect]["duration"],
                                 1 if status_effects.EFFECT_DEFS[effect].get("toggled") else 160)
                self.cast(self.actor, key + " off")
        self.assertEqual(player.practiced_skills, [])
        self.assertEqual(player.practice_exempt_skills, [])

        # A stale mastery flag/100% proficiency after demotion cannot bypass
        # the first lesson; the exemption follows the live account only.
        self.actor.account.staff_level = "player"
        for key, effect in skills.EFFECT_KEYS.items():
            player.cooldowns.clear()
            self.cast(self.actor, key)
            self.assertFalse(skills.active(player, effect))

    def test_no_resources_no_action_pending_cast_or_combat_camouflage(self):
        self.actor.player.chakra = 0
        self.cast(self.actor, "camouflage")
        self.assertFalse(skills.active(self.actor.player, "camouflage"))
        self.actor.player.chakra = 100
        self.actor.pending_cast = object()
        self.cast(self.actor, "camouflage")
        self.assertFalse(skills.active(self.actor.player, "camouflage"))
        self.actor.pending_cast = None
        self.actor.combat_target = object()
        self.cast(self.actor, "camouflage")
        self.assertFalse(skills.active(self.actor.player, "camouflage"))
        self.actor.combat_target = None
        status_effects.apply_effect(self.actor.player.active_status_effects, "stunned")
        skills.activate(self.actor, "camouflage", [])
        self.assertFalse(skills.active(self.actor.player, "camouflage"))

    def test_hidden_from_room_look_named_look_scan_and_direct_target(self):
        self.cast(self.actor, "camouflage")
        commands.cmd_look(self.viewer, [])
        self.assertNotIn("StealthNinja", "".join(self.view_output))
        self.view_output.clear()
        commands.cmd_look(self.viewer, ["StealthNinja"])
        self.assertNotIn("StealthNinja hasn't", "".join(self.view_output))
        self.actor.player.room_vnum = self.next_room.vnum
        commands.cmd_scan(self.viewer, ["north"])
        self.assertNotIn("StealthNinja is here", "".join(self.view_output))
        self.actor.player.room_vnum = self.room.vnum
        commands.cmd_attack(self.viewer, ["StealthNinja"])
        self.assertIsNone(self.viewer.pvp_target)
        before = self.viewer.player.chakra
        commands.cmd_perform(self.viewer, ["narakumi", "StealthNinja"])
        self.assertIsNone(self.viewer.pending_cast)
        self.assertEqual(self.viewer.player.chakra, before)

    def test_detection_reveals_look_scan_target_and_never_admin_invisibility(self):
        self.cast(self.actor, "camouflage")
        self.cast(self.viewer, "sensory detect")
        commands.cmd_look(self.viewer, [])
        self.assertIn("StealthNinja", "".join(self.view_output))
        self.view_output.clear()
        self.actor.player.room_vnum = self.next_room.vnum
        commands.cmd_scan(self.viewer, ["north"])
        self.assertIn("StealthNinja", "".join(self.view_output))
        self.actor.player.invisible = True
        self.assertTrue(commands._player_hidden_from(self.viewer.player, self.actor.player))
        self.actor.player.invisible = False
        self.actor.player.room_vnum = self.room.vnum
        commands.cmd_attack(self.viewer, ["StealthNinja"])
        self.assertIs(self.viewer.pvp_target, self.actor)
        self.assertFalse(skills.active(self.actor.player, "camouflage"))

    def test_concealed_cannot_be_found_or_followed_with_track_without_detection(self):
        self.cast(self.actor, "camouflage")
        import session as sessions
        self.assertIsNone(tracking.find_online_player_anywhere(sessions, "StealthNinja", viewer=self.viewer.player))
        self.viewer.player.tracking_target_player_name = "StealthNinja"
        self.assertIsNone(tracking._resolve_target_room_vnum(self.viewer.player, combat, sessions))
        self.cast(self.viewer, "sensory detect")
        self.assertIs(tracking.find_online_player_anywhere(sessions, "StealthNinja", viewer=self.viewer.player), self.actor)
        self.assertEqual(tracking._resolve_target_room_vnum(self.viewer.player, combat, sessions), self.room.vnum)

    def test_silent_walking_observers_counter_and_additional_stamina(self):
        detector, detector_output = self.make_session("Sensor")
        self.cast(detector, "sensory detect")
        self.cast(self.actor, "silent movement")
        before = self.actor.player.stamina
        with patch.object(commands.random, "randint", return_value=1):
            commands.cmd_move(self.actor, "north")
        self.assertEqual(before - self.actor.player.stamina, 3)
        self.assertNotIn("StealthNinja leaves", "".join(self.view_output))
        self.assertIn("StealthNinja leaves north", "".join(detector_output))
        self.viewer.player.room_vnum = self.next_room.vnum
        commands.cmd_look(self.viewer, [])
        self.assertIn("StealthNinja", "".join(self.view_output))  # silent is not invisibility

    def test_silent_movement_is_a_manual_toggle_without_time_limit(self):
        player = self.actor.player
        self.assertFalse(skills.active(player, "silent_movement"))
        self.cast(self.actor, "silent movement on")
        self.assertNotIn("seconds", self.output[-1])
        for _ in range(500):
            status_effects.tick_effects(player.active_status_effects)
        self.assertTrue(skills.active(player, "silent_movement"))
        self.assertIn("ON", commands._format_active_effects(player.active_status_effects))
        # Existing timed saves become persistent toggles too.
        player.active_status_effects["silent_movement"]["duration"] = 7
        restored = Player.from_dict(player.to_dict())
        for _ in range(10):
            status_effects.tick_effects(restored.active_status_effects)
        self.assertTrue(skills.active(restored, "silent_movement"))
        self.cast(self.actor, "silent movement")
        self.assertFalse(skills.active(player, "silent_movement"))
        self.assertNotIn("Moving Silently", commands._format_active_effects(player.active_status_effects))
        player.cooldowns.clear()
        self.cast(self.actor, "perform silent movement on")
        self.assertTrue(skills.active(player, "silent_movement"))
        self.cast(self.actor, "perform silent movement off")
        self.assertFalse(skills.active(player, "silent_movement"))

    def test_camouflage_movement_no_name_leak_to_either_room(self):
        destination, destination_output = self.make_session("AtDestination")
        destination.player.room_vnum = self.next_room.vnum
        self.cast(self.actor, "camouflage")
        commands.cmd_move(self.actor, "north")
        self.assertNotIn("StealthNinja", "".join(self.view_output))
        self.assertNotIn("StealthNinja", "".join(destination_output))

    def test_blocked_exit_costs_nothing_and_exhaustion_reveals_footsteps(self):
        self.cast(self.actor, "silent movement")
        before = self.actor.player.stamina
        commands.cmd_move(self.actor, "west")
        self.assertEqual(self.actor.player.stamina, before)
        self.actor.player.stamina = 1
        # A 1-Stamina walk is legal, and an exhausted stealth toggle
        # still drops when the movement upkeep cannot be paid.
        with patch.object(commands.random, "randint", return_value=1):
            commands.cmd_move(self.actor, "north")
        self.assertFalse(skills.active(self.actor.player, "silent_movement"))
        self.assertIn("StealthNinja leaves north", "".join(self.view_output))

    def test_attack_and_hostile_jutsu_reveal_caster(self):
        self.cast(self.actor, "camouflage")
        commands.cmd_attack(self.actor, ["Observer"])
        self.assertFalse(skills.active(self.actor.player, "camouflage"))
        self.actor.pvp_target = self.viewer.pvp_target = None
        self.actor.player.cooldowns["camouflage"] = 0
        self.cast(self.actor, "camouflage")
        commands.cmd_perform(self.actor, ["narakumi", "Observer"])
        self.assertFalse(skills.active(self.actor.player, "camouflage"))

    def test_sensory_upkeep_exhaustion_and_timed_expiry(self):
        self.cast(self.actor, "sensory detect")
        self.actor.player.chakra = 1
        combat.tick_effects_pulse(self.actor)
        self.assertEqual(self.actor.player.chakra, 0)
        combat.tick_effects_pulse(self.actor)
        self.assertFalse(skills.active(self.actor.player, "sensory_detect"))
        status_effects.apply_effect(self.actor.player.active_status_effects, "camouflage", duration_override=1)
        combat.tick_effects_pulse(self.actor)
        self.assertTrue(skills.active(self.actor.player, "camouflage"))
        skills.activate(self.actor, "camouflage", ["off"])
        self.assertFalse(skills.active(self.actor.player, "camouflage"))

    def test_focused_mind_duration_accuracy_and_movement_tradeoff(self):
        self.actor.player.skill_proficiencies["Focused Mind"] = 100
        self.cast(self.actor, "focused mind")
        self.assertEqual(skills.focused_duration(self.actor.player, 20), 14)
        status_effects.apply_effect(self.actor.player.active_status_effects, "confused")
        self.assertEqual(combat._accuracy_penalty_from_effects(self.actor.player), 12)
        status_effects.apply_effect(self.actor.player.active_status_effects, "blinded")
        self.assertEqual(combat._accuracy_penalty_from_effects(self.actor.player), 37)
        self.actor.player.active_status_effects.pop("confused")
        self.actor.player.active_status_effects.pop("blinded")
        before = self.actor.player.stamina
        with patch.object(commands.random, "randint", return_value=1):
            commands.cmd_move(self.actor, "north")
        self.assertEqual(before - self.actor.player.stamina, 2)

    def accuracy_conditions(self):
        """A roll of 55 misses base accuracy 50, but hits with mastered focus."""
        stack = ExitStack()
        for module, name, result in (
            (combat.derived_stats, "to_hit_chance", 50),
            (combat.derived_stats, "critical_chance", 0),
            (combat.derived_stats, "dodge_chance", 0),
            (combat.random, "randint", 55),
            (weather, "combat_accuracy_modifier", 0),
            (weather, "night_dodge_bonus", 0),
            (sage_mode, "accuracy", 0),
            (combat, "_player_attack_damage", 10),
            (combat, "roll_jutsu_damage", (20, False)),
            (combat, "_soto_uke_blocks", False),
        ):
            stack.enter_context(patch.object(module, name, return_value=result))
        return stack

    def test_focused_accuracy_scales_with_mastery_and_ends_with_effect(self):
        self.assertEqual(skills.focused_accuracy(self.actor.player), 0)
        status_effects.apply_effect(self.actor.player.active_status_effects, "focused_mind")
        for mastery, bonus in ((0, 5), (50, 7), (100, 10), (150, 10)):
            self.actor.player.skill_proficiencies["Focused Mind"] = mastery
            self.assertEqual(skills.focused_accuracy(self.actor.player), bonus)
        self.actor.player.active_status_effects.clear()
        self.assertEqual(skills.focused_accuracy(self.actor.player), 0)

    def test_focus_improves_normal_attacks_for_all_four_classes_pve_and_pvp(self):
        player = self.actor.player
        player.skill_proficiencies["Focused Mind"] = 100
        mob = combat.Mob(992718, 992718, "Accuracy Target", 25, 1000, 1000, 1, 0, 0)
        mob.room_vnum = self.room.vnum
        with self.accuracy_conditions():
            for cls in ("taijutsu", "ninjutsu", "genjutsu", "bukijutsu"):
                player.primary_class = cls
                for focused in (False, True):
                    with self.subTest(cls=cls, focused=focused):
                        player.active_status_effects.clear()
                        if focused:
                            status_effects.apply_effect(player.active_status_effects, "focused_mind")
                        mob.health = self.viewer.player.health = 1000
                        combat._player_attack_mob_once(self.actor, player, mob)
                        combat._player_attack_target_once(self.actor, player, self.viewer, self.viewer.player)
                        self.assertEqual(mob.health < 1000, focused)
                        self.assertEqual(self.viewer.player.health < 1000, focused)

    def test_focus_improves_each_classes_offensive_techniques_pve_and_pvp(self):
        player = self.actor.player
        player.skill_proficiencies["Focused Mind"] = 100
        mob = combat.Mob(992718, 992718, "Accuracy Target", 25, 1000, 1000, 1, 0, 0)
        mob.room_vnum = self.room.vnum
        roster = {"taijutsu": "choku zuki", "ninjutsu": "shadow shuriken technique",
                  "genjutsu": "narakumi", "bukijutsu": "throw kunai"}
        with self.accuracy_conditions():
            for cls, key in roster.items():
                player.primary_class = cls
                name = data_jutsu.JUTSU[key]["display_name"]
                if name not in player.learned_skills:
                    player.learned_skills.append(name)
                skill_training.mark_practiced(player, name)
                player.skill_proficiencies[name] = 100
                for focused in (False, True):
                    with self.subTest(cls=cls, focused=focused):
                        player.active_status_effects.clear()
                        self.viewer.player.active_status_effects.clear()
                        if focused:
                            status_effects.apply_effect(player.active_status_effects, "focused_mind")
                        mob.health = self.viewer.player.health = 1000
                        player.inventory = ["Kunai"]
                        player.cooldowns.clear()
                        combat.use_jutsu(self.actor, key, mob)
                        player.inventory = ["Kunai"]
                        player.cooldowns.clear()
                        combat.use_jutsu_on_player(self.actor, key, self.viewer)
                        self.assertEqual(mob.health < 1000, focused)
                        self.assertEqual(self.viewer.player.health < 1000, focused)

    def test_focused_mind_shortens_real_pvp_genjutsu_status(self):
        self.actor.player.skill_proficiencies["Focused Mind"] = 100
        self.cast(self.actor, "focused mind")
        self.viewer.player.practice_gate_enabled = False
        self.viewer.player.learned_skills.append("Narakumi")
        self.viewer.player.skill_proficiencies["Narakumi"] = 100
        with patch.object(combat.random, "randint", return_value=1), \
                patch.object(combat.derived_stats, "dodge_chance", return_value=-100):
            combat.use_jutsu_on_player(self.viewer, "narakumi", self.actor)
        self.assertEqual(self.actor.player.active_status_effects["narakumi"]["duration"], 16)

    def test_focused_mind_shortens_room_sleep_without_granting_immunity(self):
        self.actor.player.skill_proficiencies["Focused Mind"] = 100
        self.cast(self.actor, "focused mind")
        info = data_jutsu.JUTSU["nehan shouja"]
        self.viewer.player.learned_skills.append(info["display_name"])
        self.viewer.player.practice_gate_enabled = False
        with patch.object(genjutsu.random, "randint", return_value=1):
            genjutsu.resolve_cast(self.viewer, "nehan shouja", {
                "kind": "room_sleep", "room_vnum": self.room.vnum})
        self.assertEqual(self.actor.player.active_status_effects["asleep"]["duration"], 8)

    def test_camouflage_prevents_normal_mob_aggression_but_sensors_can_engage(self):
        mob = combat.Mob(992719, 992719, "Alert Guard", 25, 200, 200, 1, 0, 0)
        mob.room_vnum = self.room.vnum
        combat.MOBS_BY_ROOM[self.room.vnum] = [mob]
        combat.MOB_TEMPLATES[mob.template_vnum] = {"act_flags": ["aggressive_everyone"]}
        self.addCleanup(combat.MOBS_BY_ROOM.pop, self.room.vnum, None)
        self.addCleanup(combat.MOB_TEMPLATES.pop, mob.template_vnum, None)
        self.cast(self.actor, "camouflage")
        mob_aggression.process_aggression()
        self.assertIsNone(self.actor.combat_target)
        status_effects.apply_effect(mob.active_status_effects, "sensory_detect")
        mob_aggression.process_aggression()
        self.assertIs(self.actor.combat_target, mob)
        self.assertFalse(skills.active(self.actor.player, "camouflage"))

    def test_hidden_mist_still_has_its_own_rules(self):
        self.cast(self.viewer, "sensory detect")
        self.room.hidden_mist_caster = self.actor.player.name
        self.room.hidden_mist_expires_at = 10**15
        self.assertTrue(hidden_mist.conceals_from_view(self.viewer.player, self.actor.player))
        self.assertTrue(commands._player_hidden_from(self.viewer.player, self.actor.player))


if __name__ == "__main__":
    unittest.main()
