"""Target omission follows real combat, including autonomous mob aggression."""
import unittest
from unittest.mock import patch

import combat
import commands
import content
import data_jutsu
import general_skills
import mob_aggression
import session as sessions
import world
from models import Account, Player
from session import Session, State


class DefaultJutsuTargetTests(unittest.TestCase):
    def setUp(self):
        for item in (patch.object(world.WORLD, "rooms", {}),
                     patch.object(combat, "MOBS_BY_ROOM", {}),
                     patch.object(combat, "MOB_TEMPLATES", {}),
                     patch.object(sessions, "ACTIVE_SESSIONS", [])):
            item.start()
            self.addCleanup(item.stop)
        self.room = world.Room(992830, "Combat Clearing", "Open ground.")
        world.WORLD.add_room(self.room)
        self.out = []
        self.s = Session(self.out.append, lambda: None)
        self.s.player = Player("Caster", "Caster", level=100, room_vnum=self.room.vnum,
                               chakra=1000, stamina=1000, primary_class="taijutsu")
        self.s.account = Account("Caster", "salt", "hash", staff_level="player")
        self.s.state = State.PLAYING
        self.s.player.learned_skills = [j["display_name"] for j in data_jutsu.JUTSU.values()]
        self.s.player.skill_proficiencies = {name: 100 for name in self.s.player.learned_skills}
        combat.register_template(992831, "Bandit", 30, 1000, 1, 2, 0, 0)
        self.first = combat.spawn_mob(992831, self.room.vnum)
        self.second = combat.spawn_mob(992831, self.room.vnum)

    def test_attack_jutsu_uses_current_duplicate_mob_and_explicit_target_wins(self):
        self.s.combat_target = self.second
        with patch.object(combat, "use_jutsu") as cast:
            commands.cmd_use_jutsu(self.s, "dynamic entry", [])
            self.assertIs(cast.call_args.args[2], self.second)
            commands.cmd_use_jutsu(self.s, "dynamic entry", ["1.bandit"])
            self.assertIs(cast.call_args.args[2], self.first)

    def test_actual_npc_aggro_sets_target_for_jutsu(self):
        combat.MOB_TEMPLATES[992831]["act_flags"] = ["aggressive_everyone"]
        with patch.object(combat, "_mob_attack_damage", return_value=1):
            mob_aggression.process_aggression()
        self.assertIsNotNone(self.s.combat_target)
        target = self.s.combat_target
        with patch.object(combat, "use_jutsu") as cast:
            commands.cmd_use_jutsu(self.s, "dynamic entry", [])
            self.assertIs(cast.call_args.args[2], target)

    def test_player_aggro_supplies_special_jutsu_and_self_skills_stay_self(self):
        other = Session(lambda text: None, lambda: None)
        other.player = Player("Rival", "Rival", room_vnum=self.room.vnum)
        other.state = State.PLAYING
        combat.start_pvp_attack(other, self.s)
        with patch("reaper_seal.cast") as cast:
            commands.cmd_use_jutsu(self.s, "reaper death seal", [])
            self.assertEqual(cast.call_args.args[2], ["Rival"])
        with patch.object(general_skills, "activate") as cast:
            commands.cmd_use_jutsu(self.s, "silent movement", [])
            self.assertEqual(cast.call_args.args[2], [])

    def test_special_mangekyo_and_instant_kill_use_current_mob(self):
        self.s.combat_target = self.second
        self.s.account.staff_level = "implementor"
        import mangekyo_mobs
        import legacy_techniques
        with patch.object(mangekyo_mobs, "cast") as cast:
            commands.cmd_use_jutsu(self.s, "amaterasu", [])
            self.assertIs(cast.call_args.args[2], self.second)
        with patch.object(legacy_techniques, "instant_kill") as cast:
            commands.cmd_use_jutsu(self.s, "1000 years of death", [])
            self.assertEqual(cast.call_args.args[1], ["2.Bandit"])

    def test_player_opponent_is_not_confused_with_npc_of_same_name(self):
        other = Session(lambda text: None, lambda: None)
        other.player = Player("Bandit", "Bandit", room_vnum=self.room.vnum)
        other.state = State.PLAYING
        combat.start_pvp_attack(self.s, other)
        with patch.object(combat, "use_jutsu_on_player") as cast, patch.object(combat, "use_jutsu") as npc_cast:
            commands.cmd_use_jutsu(self.s, "dynamic entry", [])
            self.assertIs(cast.call_args.args[2], other)
            npc_cast.assert_not_called()

    def test_dead_missing_and_other_room_opponents_are_never_reused(self):
        self.s.combat_target = self.first
        self.first.health = 0
        self.assertEqual(commands._current_jutsu_opponent(self.s), [])
        self.first.health = 1
        self.first.room_vnum += 1
        self.assertEqual(commands._current_jutsu_opponent(self.s), [])
        self.first.room_vnum = self.room.vnum
        combat.MOBS_BY_ROOM[self.room.vnum].remove(self.first)
        self.assertEqual(commands._current_jutsu_opponent(self.s), [])


if __name__ == "__main__":
    unittest.main()
