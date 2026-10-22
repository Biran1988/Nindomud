"""Mastered elemental-clone reconnaissance and hostile village/clan/all NPCs."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import clone_control
import combat
import commands
import mob_aggression
import session as session_module
import world
from models import Player


class CloneAndAggressionTests(unittest.TestCase):
    def setUp(self):
        # Most tests mock room rendering; retain the real look handler for
        # first-person visibility tests.
        self.real_cmd_look = commands.cmd_look
        self.patches = [
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(combat, "MOB_TEMPLATES", {}),
            patch.object(world.WORLD, "rooms", {}),
            patch.object(session_module, "ACTIVE_SESSIONS", []),
            patch.object(commands, "cmd_look"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        mob_aggression._clone_attack_due.clear()
        for vnum in (5001, 5002, 5003):
            world.WORLD.add_room(world.Room(vnum, f"Area {vnum}", "A wilderness area."))
        world.WORLD.rooms[5001].exits["north"] = 5002
        world.WORLD.rooms[5002].exits["south"] = 5001
        world.WORLD.rooms[5002].exits["east"] = 5003
        world.WORLD.rooms[5003].exits["west"] = 5002
        p = Player(name="Scout", account_name="Scout", level=55, primary_class="ninjutsu")
        p.room_vnum = 5001
        p.village = "leaf"
        p.clan = "uchiha"
        p.maximum_health = 200
        p.chakra = 200
        p.skill_proficiencies["Shadow Clone Jutsu"] = 100
        p.skill_proficiencies["Mizu Bunshin"] = 100
        self.player = p
        self.session = NS(player=p, account=NS(name="Scout", staff_level="player"),
                          state=NS(name="PLAYING"),
                          controlled_clone=None, combat_target=None,
                          pvp_target=None, duel=None, pending_action=None,
                          pending_cast=None, chakra_charge=None,
                          send=Mock(), send_prompt=Mock())
        self.session.active_sessions = lambda: [self.session]
        session_module.ACTIVE_SESSIONS.append(self.session)
        self.clone = combat.spawn_shadow_clones(p, 1, "water")[0]

    def test_control_requires_elemental_jutsu_mastery_and_no_combat(self):
        self.player.skill_proficiencies["Mizu Bunshin"] = 99
        clone_control.cmd_clone(self.session, ["control"])
        self.assertIsNone(self.session.controlled_clone)
        self.player.skill_proficiencies["Mizu Bunshin"] = 100
        self.session.combat_target = NS(name="enemy")
        clone_control.cmd_clone(self.session, ["control"])
        self.assertIsNone(self.session.controlled_clone)
        self.assertIn("during combat", self.session.send.call_args.args[0])
        self.session.combat_target = None
        clone_control.cmd_clone(self.session, ["control"])
        self.assertIs(self.session.controlled_clone, self.clone)
        self.assertEqual(self.player.room_vnum, 5001)
        self.assertEqual(self.clone.name, "Scout")

    def test_level_works_in_clone_view_without_moving_real_body(self):
        self.player.experience = 123456
        clone_control.cmd_clone(self.session, ["control"])
        self.session.send.reset_mock()
        self.assertTrue(clone_control.handle_playing_command(self.session, "level"))
        shown = self.session.send.call_args.args[0]
        self.assertIn("XP Needed", shown)
        self.assertIn("123456", shown)
        self.assertIs(self.session.player, self.player)
        self.assertEqual(self.player.room_vnum, 5001)

    def test_clone_moves_independently_of_real_body(self):
        clone_control.cmd_clone(self.session, ["control"])
        self.assertTrue(clone_control.handle_playing_command(self.session, "north"))
        self.assertEqual(self.clone.room_vnum, 5002)
        self.assertEqual(self.player.room_vnum, 5001)
        self.assertIn(self.clone, combat.MOBS_BY_ROOM[5002])
        self.assertNotIn(self.clone, combat.MOBS_BY_ROOM[5001])
        self.assertTrue(clone_control.handle_playing_command(self.session, "east"))
        self.assertEqual(self.clone.room_vnum, 5003)
        self.assertEqual(clone_control.view_room(self.session), 5003)
        self.assertEqual(self.player.room_vnum, 5001)

    def test_clone_look_sees_own_unmoved_body_in_original_room(self):
        clone_control.cmd_clone(self.session, ["control"])
        self.assertIs(self.session.player, self.player)
        with patch.object(commands, "cmd_look", self.real_cmd_look):
            self.session.send.reset_mock()
            clone_control.handle_playing_command(self.session, "look")
            text = "\n".join(call.args[0] for call in self.session.send.call_args_list)
            self.assertIn("  &GScout&x is here.", text)
            self.assertNotIn("motionless", text)
            self.assertNotIn("consciousness", text)
            self.assertIs(self.session.player, self.player)
            self.assertEqual(self.player.room_vnum, 5001)
            self.session.send.reset_mock()
            clone_control.handle_playing_command(self.session, "look Scout")
            text = "\n".join(call.args[0] for call in self.session.send.call_args_list)
            self.assertIn("Scout", text)
            self.assertNotIn("original body", text)
            self.assertNotIn("reconnaissance", text)

            clone_control.handle_playing_command(self.session, "north")
            self.session.send.reset_mock()
            clone_control.handle_playing_command(self.session, "look")
            away = "\n".join(call.args[0] for call in self.session.send.call_args_list)
            self.assertNotIn("  &GScout&x is here.", away)
            self.assertEqual(self.player.room_vnum, 5001)
            self.assertIs(self.session.player, self.player)

            clone_control.handle_playing_command(self.session, "south")
            self.session.send.reset_mock()
            clone_control.handle_playing_command(self.session, "look")
            returned = "\n".join(call.args[0] for call in self.session.send.call_args_list)
            self.assertIn("  &GScout&x is here.", returned)
            self.assertEqual(self.player.room_vnum, 5001)

    def test_clone_scan_shows_real_body_without_a_remote_control_label(self):
        self.player.learned_skills.append("Scan")
        clone_control.cmd_clone(self.session, ["control"])
        clone_control.handle_playing_command(self.session, "north")
        self.session.send.reset_mock()
        clone_control.handle_playing_command(self.session, "scan south")
        messages = "\n".join(c.args[0] for c in self.session.send.call_args_list)
        self.assertIn("  &GScout&x is here.", messages)
        self.assertNotIn("motionless", messages)
        self.assertNotIn("controlling a clone", messages)

    def test_pilot_sees_only_the_room_while_observers_see_normal_travel(self):
        observer_a = NS(player=Player("Watcher", "Watcher", room_vnum=5001),
                        combat_target=None, pvp_target=None, send=Mock())
        observer_b = NS(player=Player("Guard", "Guard", room_vnum=5002),
                        combat_target=None, pvp_target=None, send=Mock())
        session_module.ACTIVE_SESSIONS.extend([observer_a, observer_b])
        clone_control.cmd_clone(self.session, ["control"])
        self.session.send.reset_mock()
        clone_control.handle_playing_command(self.session, "north")
        messages = "\n".join(call.args[0] for call in self.session.send.call_args_list)
        self.assertNotIn("You guide your clone", messages)
        self.assertNotIn("leaves north", messages)
        self.assertNotIn("arrives from the south", messages)
        self.assertIn("Scout leaves north.", observer_a.send.call_args.args[0])
        self.assertIn("Scout arrives from the south.", observer_b.send.call_args.args[0])
        self.assertIs(self.session.player, self.player)
        self.assertEqual(self.player.room_vnum, 5001)

    def test_clone_and_real_body_both_look_like_ordinary_players(self):
        body_observer = NS(player=Player("BodyWitness", "BodyWitness", room_vnum=5001),
                           account=NS(staff_level="player"), controlled_clone=None,
                           combat_target=None, pvp_target=None, send=Mock())
        clone_observer = NS(player=Player("CloneWitness", "CloneWitness", room_vnum=5002),
                            account=NS(staff_level="player"), controlled_clone=None,
                            combat_target=None, pvp_target=None, send=Mock())
        session_module.ACTIVE_SESSIONS.extend([body_observer, clone_observer])
        for observer in (body_observer, clone_observer):
            observer.active_sessions = lambda: session_module.ACTIVE_SESSIONS
        self.session.active_sessions = lambda: session_module.ACTIVE_SESSIONS

        clone_control.cmd_clone(self.session, ["control"])
        clone_control.handle_playing_command(self.session, "north")
        self.real_cmd_look(body_observer, [])
        body_text = "\n".join(c.args[0] for c in body_observer.send.call_args_list)
        self.assertIn("  &GScout&x is here.", body_text)
        self.assertNotIn("motionless", body_text)
        self.assertNotIn("clone", body_text.lower())

        self.real_cmd_look(clone_observer, [])
        clone_text = "\n".join(c.args[0] for c in clone_observer.send.call_args_list)
        self.assertIn("  &GScout&x is here.", clone_text)
        self.assertNotIn("water clone", clone_text.lower())
        self.assertNotIn("reconnaissance", clone_text.lower())
        self.real_cmd_look(clone_observer, ["Scout"])
        examined = clone_observer.send.call_args.args[0]
        self.assertIn("Scout", examined)
        self.assertNotIn("clone", examined.lower())

    def test_clone_speech_and_socials_use_normal_character_identity(self):
        import chat_moderation
        import emotes
        body_observer = NS(player=Player("BodyWitness", "BodyWitness", room_vnum=5001),
                           controlled_clone=None, combat_target=None,
                           pvp_target=None, send=Mock())
        clone_observer = NS(player=Player("CloneWitness", "CloneWitness", room_vnum=5002),
                            controlled_clone=None, combat_target=None,
                            pvp_target=None, send=Mock())
        session_module.ACTIVE_SESSIONS.extend([body_observer, clone_observer])
        clone_control.cmd_clone(self.session, ["control"])
        clone_control.handle_playing_command(self.session, "north")
        self.session.send.reset_mock()
        clone_observer.send.reset_mock()
        body_observer.send.reset_mock()
        with patch.object(commands, "_is_silenced", return_value=False), \
             patch.object(chat_moderation, "record_and_check_spam", return_value=False):
            clone_control.handle_playing_command(self.session, "say Hello there")
            self.assertEqual(self.session.send.call_args.args[0],
                             "&gYou say, 'Hello there'&x")
            self.assertEqual(clone_observer.send.call_args.args[0],
                             "&gScout says, 'Hello there'&x")
            self.assertFalse(body_observer.send.called)
            self.session.send.reset_mock()
            clone_observer.send.reset_mock()
            with patch.dict(emotes.EMOTES, {"testnod": ("nod.", "nods.")}):
                clone_control.handle_playing_command(self.session, "@testnod")
            self.assertEqual(self.session.send.call_args.args[0], "You nod.")
            self.assertEqual(clone_observer.send.call_args.args[0], "Scout nods.")
            self.assertFalse(body_observer.send.called)

    def test_clone_cannot_revert_using_quit_recall_combat_or_other_body_commands(self):
        clone_control.cmd_clone(self.session, ["control"])
        for command in ("recall", "attack bandit", "perform rasengan bandit",
                        "quit", "save", "clone control", "goto 5002", "flee"):
            self.assertTrue(clone_control.handle_playing_command(self.session, command))
            self.assertIs(self.session.controlled_clone, self.clone)
            self.assertEqual(self.player.room_vnum, 5001)
        self.assertEqual(clone_control.view_room(self.session), 5001)

    def test_disperse_returns_to_body_and_does_not_deplete_body(self):
        clone_control.cmd_clone(self.session, ["control"])
        clone_control.handle_playing_command(self.session, "north")
        clone_control.cmd_clone(self.session, ["disperse"])
        self.assertIsNone(self.session.controlled_clone)
        self.assertNotIn(self.clone, combat.MOBS_BY_ROOM[5002])
        self.assertEqual(self.player.room_vnum, 5001)
        self.assertFalse(combat.active_shadow_clones(self.player))

    def test_clone_defeat_restores_viewpoint_without_player_death(self):
        clone_control.cmd_clone(self.session, ["control"])
        clone_control.handle_playing_command(self.session, "north")
        attacker = NS(player=Player("Hunter", "Hunter"), send=Mock(), combat_target=self.clone)
        self.clone.health = 0
        combat.handle_mob_defeat(attacker, self.clone)
        self.assertIsNone(self.session.controlled_clone)
        self.assertEqual(self.player.room_vnum, 5001)
        self.assertEqual(self.player.health, 100)
        self.assertNotIn(self.clone, combat.MOBS_BY_ROOM[5002])

    def test_too_little_chakra_disperses_controlled_clone(self):
        clone_control.cmd_clone(self.session, ["control"])
        self.player.chakra = 0
        combat.tick_shadow_clone_upkeep(self.player)
        self.assertIsNone(self.session.controlled_clone)
        self.assertEqual(self.player.room_vnum, 5001)

    def test_aggression_flags_match_exact_village_and_clan(self):
        template = {"act_flags": ["aggressive_village"], "aggro_village": "leaf",
                    "aggro_clan": ""}
        self.assertTrue(mob_aggression.targets_player(template, self.player))
        template["aggro_village"] = "sand"
        self.assertFalse(mob_aggression.targets_player(template, self.player))
        template["act_flags"] = ["aggressive_clan"]
        template["aggro_clan"] = "uchiha"
        self.assertTrue(mob_aggression.targets_player(template, self.player))
        template["aggro_clan"] = "hyuga"
        self.assertFalse(mob_aggression.targets_player(template, self.player))
        template["act_flags"] = ["aggressive_everyone"]
        self.assertTrue(mob_aggression.targets_player(template, self.player))
        template["act_flags"] = ["aggressive_clan", "aggressive_village"]
        template["aggro_village"] = "leaf"
        self.assertTrue(mob_aggression.targets_player(template, self.player))

    def test_aggressive_mob_starts_real_combat_and_respects_safe_room(self):
        combat.register_template(9510, "Rogue ninja", 20, 100, 1, 6, 50, 10)
        combat.MOB_TEMPLATES[9510]["act_flags"] = ["Npc", "aggressive_village"]
        combat.MOB_TEMPLATES[9510]["aggro_village"] = "leaf"
        enemy = combat.spawn_mob(9510, 5001)
        world.WORLD.rooms[5001].safe = True
        mob_aggression.process_aggression(now=100)
        self.assertIsNone(self.session.combat_target)
        world.WORLD.rooms[5001].safe = False
        mob_aggression.process_aggression(now=101)
        self.assertIs(self.session.combat_target, enemy)

    def test_aggressive_mob_can_defeat_scout_without_killing_caster(self):
        clone_control.cmd_clone(self.session, ["control"])
        clone_control.handle_playing_command(self.session, "north")
        combat.register_template(9511, "Ambush bandit", 15, 100, 1, 10, 50, 2)
        combat.MOB_TEMPLATES[9511]["act_flags"] = ["Npc", "aggressive_everyone"]
        combat.spawn_mob(9511, 5002)
        self.clone.health = 2
        with patch.object(combat, "_mob_attack_damage", return_value=3):
            mob_aggression.process_aggression(now=1000)
        self.assertIsNone(self.session.controlled_clone)
        self.assertEqual(self.player.room_vnum, 5001)
        self.assertEqual(self.player.health, 100)
        self.assertNotIn(self.clone, combat.MOBS_BY_ROOM[5002])


if __name__ == "__main__":
    unittest.main()
