"""Private scroll eligibility, durable paired capture and mask-gated release."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import combat
import commands
import content
import data_jutsu
import help_system
import leveling
import olc
import reaper_seal as rite
import session as sessions
import storage
import world
import world_persistence
from models import Account, Player
from session import Session, State


class ReaperSealTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for item in (patch.object(storage, "DATA_DIR", tmp.name),
                     patch.object(storage, "PLAYERS_DIR", os.path.join(tmp.name, "players")),
                     patch.object(storage, "ACCOUNTS_DIR", os.path.join(tmp.name, "accounts")),
                     patch.object(world.WORLD, "rooms", {}),
                     patch.object(combat, "MOBS_BY_ROOM", {}),
                     patch.object(combat, "MOB_TEMPLATES", {}),
                     patch.object(olc, "OBJECT_TEMPLATES", {}),
                     patch.object(sessions, "ACTIVE_SESSIONS", [])):
            item.start()
            self.addCleanup(item.stop)
        world.WORLD.add_room(world.Room(1, "Clearing", "Open ground."))
        world.WORLD.add_room(world.Room(2, "Home", "A quiet room.", safe=True))
        rite.register_items()
        self.caster, self.out = self.make_session("Sealer")
        self.target, self.target_out = self.make_session("Victim", village="leaf", clan="nara")
        self.rescuer, self.rescue_out = self.make_session("Rescuer")

    def make_session(self, name, **kwargs):
        out = []
        s = Session(out.append, lambda: None)
        s.player = Player(name, name, village=kwargs.get("village", "whirlpool"),
                          clan=kwargs.get("clan", "uzumaki"), primary_class="ninjutsu",
                          level=25, room_vnum=1, chakra=1000)
        s.account = Account(name, "salt", "hash")
        s.state = State.PLAYING
        storage.save_player(s.player)
        out.clear()
        return s, out

    def learn(self, s):
        if rite.SCROLL_NAME not in s.player.inventory:
            s.player.inventory.append(rite.SCROLL_NAME)
        commands.cmd_read(s, ["reaper"])
        self.assertIn("Reaper Death Seal", s.player.learned_skills)
        self.assertIn("Reverse Reaper Seal", s.player.learned_skills)
        s.player.skill_proficiencies["Reaper Death Seal"] = 100

    def capture(self):
        self.learn(self.caster)
        commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        self.assertTrue(rite.imprisoned(self.caster.player), self.out)
        self.assertEqual(self.caster.player.reaper_seal_id, self.target.player.reaper_seal_id)

    def reverse(self):
        self.learn(self.rescuer)
        self.rescuer.player.equipment["head"] = rite.MASK_NAME
        commands.dispatch_line(self.rescuer, "perform reverse reaper seal Victim")

    def test_hidden_scroll_only_level_clan_and_village_gates(self):
        for village, clan, level in (("leaf", "uzumaki", 25), ("whirlpool", "nara", 25),
                                     ("whirlpool", "uzumaki", 24)):
            p = self.caster.player
            p.village, p.clan, p.level = village, clan, level
            p.inventory = [rite.SCROLL_NAME]
            commands.cmd_read(self.caster, ["reaper"])
            self.assertNotIn("Reaper Death Seal", p.learned_skills)
            self.assertEqual(p.inventory, [rite.SCROLL_NAME])
        p.village, p.clan, p.level = "whirlpool", "uzumaki", 25
        leveling.sync_universal_skills(p)
        self.assertNotIn("Reaper Death Seal", p.learned_skills)
        self.assertNotIn("Reaper Death Seal", "\n".join(commands.build_jutsu_catalog_lines(p)))
        self.assertFalse(any("reaper" in str(entry).lower() for entry in help_system.DEFAULT_HELP_ENTRIES))
        import changelog
        self.assertFalse(any("reaper" in message.lower() or "shikigami" in message.lower()
                             for _, message in changelog.CHANGELOG))
        self.learn(self.caster)
        self.assertNotIn(rite.SCROLL_NAME, p.inventory)

    def test_pair_cannot_escape_through_commands_direct_travel_or_relogin(self):
        self.capture()
        room = self.caster.player.room_vnum
        self.assertTrue(world.WORLD.get(room).reaper_prison)
        self.assertEqual(world.WORLD.get(room).exits, {})
        for s in (self.caster, self.target):
            for command in ("north", "recall", "anki", "goto 2", "teleport halloween",
                            "perform kamui self", "perform reverse reaper seal Victim", "flee"):
                s.handle_line(command)
                self.assertEqual(s.player.room_vnum, room, command)
            s.player.room_vnum = 2  # all direct teleports share the same lock
            self.assertEqual(s.player.room_vnum, room)
        self.caster.request_close()
        loaded = storage.load_player("Sealer")
        self.assertEqual(loaded.room_vnum, room)
        self.assertTrue(rite.imprisoned(loaded))
        self.assertNotIn(str(room), world_persistence.snapshot_world()["rooms"])

    def test_release_requires_wearing_mask_and_frees_both_players(self):
        self.capture()
        self.learn(self.rescuer)
        self.rescuer.player.inventory.append(rite.MASK_NAME)
        commands.dispatch_line(self.rescuer, "perform reverse reaper seal Victim")
        self.assertTrue(rite.imprisoned(self.target.player))
        commands.cmd_wear(self.rescuer, ["shikigami"])
        commands.dispatch_line(self.rescuer, "perform reverse reaper seal Victim")
        self.assertFalse(rite.imprisoned(self.target.player), self.rescue_out)
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertEqual(self.rescuer.player.equipment["head"], rite.MASK_NAME)

    def test_reboot_and_offline_release_use_authoritative_pair_journal(self):
        self.capture()
        room = self.target.player.room_vnum
        # Reconstruct rooms from durable state with nobody online.
        sessions.ACTIVE_SESSIONS.clear()
        world.WORLD.rooms.pop(room)
        rite.restore_world()
        self.assertIsNotNone(world.WORLD.get(room))
        self.assertEqual(storage.load_player("Victim").room_vnum, room)
        sessions.ACTIVE_SESSIONS.append(self.rescuer)
        self.reverse()
        for name in ("Sealer", "Victim"):
            player = storage.load_player(name)
            self.assertFalse(rite.imprisoned(player))
            self.assertEqual(player.room_vnum, 1)

    def test_failure_safe_room_and_unknown_target_never_imprison(self):
        self.learn(self.caster)
        self.caster.player.skill_proficiencies["Reaper Death Seal"] = 1
        with patch.object(rite.random, "randint", return_value=100):
            commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertFalse(rite.imprisoned(self.target.player))
        self.caster.player.cooldowns.clear()
        world.WORLD.get(1).safe = True
        self.caster.player.skill_proficiencies["Reaper Death Seal"] = 100
        commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        self.assertFalse(rite.imprisoned(self.target.player))
        world.WORLD.get(1).safe = False
        before = self.caster.player.chakra
        commands.dispatch_line(self.caster, "perform reaper death seal nobody")
        self.assertEqual(self.caster.player.chakra, before)

    def test_npc_target_cannot_be_sealed_or_consume_chakra(self):
        self.learn(self.caster)
        combat.register_template(99181, "Orochimaru", 100, 1000, 10, 20, 0, 0)
        mob = combat.spawn_mob(99181, 1)
        before = self.caster.player.chakra
        commands.dispatch_line(self.caster, "perform reaper death seal Orochimaru")
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertIn(mob, combat.mobs_in_room(1))
        self.assertEqual(self.caster.player.chakra, before)
        self.assertIn("never an NPC", "".join(self.out))


if __name__ == "__main__":
    unittest.main()
