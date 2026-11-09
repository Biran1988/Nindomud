"""Private scroll eligibility, durable paired capture and mask-gated release."""
import json
import os
import tempfile
import time
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
        s.player.pvp_organization = 'akatsuki' if name == 'Sealer' else 'anbu'
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
        # Mask in inventory OR worn may reverse the imprisonment.
        commands.cmd_wear(self.rescuer, ["shikigami"])
        commands.dispatch_line(self.rescuer, "perform reverse reaper seal Victim")
        self.assertFalse(rite.imprisoned(self.target.player), self.rescue_out)
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertEqual(self.rescuer.player.equipment["head"], rite.MASK_NAME)

    def test_wearing_mask_allows_reverse_from_inside_stomach(self):
        self.capture()
        self.caster.player.equipment["head"] = rite.MASK_NAME
        commands.dispatch_line(self.caster, "perform reverse reaper seal Victim")
        self.assertFalse(rite.imprisoned(self.caster.player), self.out)
        self.assertFalse(rite.imprisoned(self.target.player), self.out)
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertEqual(self.target.player.room_vnum, 1)

    def test_mortal_caster_can_seal_immortal_target_without_restricting_staff(self):
        self.learn(self.caster)
        self.target.account.staff_level = "implementor"
        # A staff character's existing effects and chakra must not be
        # removed just because the rite transports them to the prison.
        self.target.player.active_status_effects["custom_buff"] = {"duration": 999}
        original_chakra = self.target.player.chakra
        commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        prison = self.caster.player.room_vnum
        self.assertTrue(rite.imprisoned(self.caster.player), self.out)
        self.assertTrue(world.WORLD.get(prison).reaper_prison)
        self.assertEqual(self.target.player.room_vnum, prison)
        self.assertFalse(rite.imprisoned(self.target.player))
        self.assertIsNone(self.target.player.reaper_seal_room_vnum)
        self.assertIn("custom_buff", self.target.player.active_status_effects)
        self.assertEqual(self.target.player.chakra, original_chakra)
        self.assertIn("Victim", next(iter(rite._load().values()))["unbound_staff"])
        self.target.player.room_vnum = 2
        self.assertEqual(self.target.player.room_vnum, 2)
        commands.dispatch_line(self.target, "goto 1")
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertTrue(rite.imprisoned(self.caster.player))
        saved_staff = storage.load_player("Victim")
        self.assertFalse(rite.imprisoned(saved_staff))
        self.assertEqual(saved_staff.room_vnum, prison)

    def test_immortal_caster_can_cast_without_scroll_clan_chakra_or_cooldown(self):
        self.caster.account.staff_level = "implementor"
        self.caster.player.village = "leaf"
        self.caster.player.clan = "nara"
        self.caster.player.level = 1
        self.caster.player.chakra = 1
        self.caster.player.cooldowns[rite.SEAL_KEY] = time.time() + 9999
        self.caster.player.active_status_effects["custom_buff"] = {"duration": 999}
        commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        self.assertTrue(rite.imprisoned(self.target.player), self.out)
        prison = self.target.player.room_vnum
        self.assertEqual(self.caster.player.room_vnum, prison)
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertEqual(self.caster.player.chakra, 1)
        self.assertIn("custom_buff", self.caster.player.active_status_effects)
        # Immortal may use staff travel without undoing mortal's seal.
        commands.dispatch_line(self.caster, "goto 2")
        self.assertEqual(self.caster.player.room_vnum, 2)
        self.assertTrue(rite.imprisoned(self.target.player))
        storage.save_player(self.caster.player)
        self.assertFalse(rite.imprisoned(storage.load_player("Sealer")))

    def test_two_immortals_enter_stomach_but_both_can_leave(self):
        self.caster.account.staff_level = "implementor"
        self.target.account.staff_level = "implementor"
        commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        room = self.caster.player.room_vnum
        self.assertTrue(world.WORLD.get(room).reaper_prison, self.out)
        self.assertEqual(self.target.player.room_vnum, room)
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertFalse(rite.imprisoned(self.target.player))
        self.caster.player.room_vnum = 1
        self.target.player.room_vnum = 2
        self.assertEqual(self.caster.player.room_vnum, 1)
        self.assertEqual(self.target.player.room_vnum, 2)

    def test_staff_promotion_unlocks_legacy_seal_without_freeing_mortal(self):
        self.capture()
        prison = self.caster.player.room_vnum
        self.assertEqual(self.target.player.room_vnum, prison)
        self.caster.account.staff_level = "implementor"
        commands.dispatch_line(self.caster, "goto 2")
        self.assertEqual(self.caster.player.room_vnum, 2, self.out)
        self.assertFalse(rite.imprisoned(self.caster.player))
        self.assertTrue(rite.imprisoned(self.target.player))
        sealed = next(iter(rite._load().values()))
        self.assertIn("Sealer", sealed["unbound_staff"])
        self.assertTrue(sealed["active"])
        storage.save_player(self.caster.player)
        reloaded = storage.load_player("Sealer")
        self.assertFalse(rite.imprisoned(reloaded))
        self.assertEqual(reloaded.room_vnum, 2)

    def test_reversing_immortal_cast_releases_mortal_without_dragging_staff(self):
        self.caster.account.staff_level = "implementor"
        commands.dispatch_line(self.caster, "perform reaper death seal Victim")
        self.assertTrue(rite.imprisoned(self.target.player))
        commands.dispatch_line(self.caster, "goto 2")
        self.assertEqual(self.caster.player.room_vnum, 2)
        # Staff may reverse from outside, without mask or skill gates.
        commands.dispatch_line(self.caster, "perform reverse reaper seal Victim")
        self.assertFalse(rite.imprisoned(self.target.player))
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertEqual(self.caster.player.room_vnum, 2)

    def test_trapped_player_can_reverse_with_carried_mask(self):
        self.capture()
        self.caster.player.inventory.append(rite.MASK_NAME)
        commands.dispatch_line(self.caster, "perform reverse reaper seal")
        self.assertFalse(rite.imprisoned(self.caster.player), self.out)
        self.assertEqual(self.caster.player.room_vnum, 1)

    def test_trapped_immortal_can_reverse_legacy_seal_without_mask(self):
        self.capture()
        self.caster.account.staff_level = "immortal"  # previously trapped staff account
        commands.dispatch_line(self.caster, "perform reverse reaper seal")
        self.assertFalse(rite.imprisoned(self.caster.player), self.out)
        self.assertFalse(rite.imprisoned(self.target.player), self.out)
        self.assertEqual(self.caster.player.room_vnum, 1)

    def test_staff_can_reverse_without_clan_scroll_or_mask(self):
        self.capture()
        self.rescuer.account.staff_level = "immortal"
        self.rescuer.player.village = "leaf"
        self.rescuer.player.clan = "nara"
        commands.dispatch_line(self.rescuer, "perform reverse reaper seal Victim")
        self.assertFalse(rite.imprisoned(self.caster.player), self.rescue_out)
        self.assertFalse(rite.imprisoned(self.target.player), self.rescue_out)

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
