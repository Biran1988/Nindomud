"""Regressions for room-tag traps, skill unlocks and reserved scroll VNUM."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import combat
import commands
import data_jutsu
import jutsu_scroll_catalog
import leveling
import olc
import room_trap_tags as tags
import skill_training
import storage
import world
from models import Player


class RoomTrapTagTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for obj, attr, val in (
            (storage, "DATA_DIR", tmp.name),
            (olc, "OBJECT_TEMPLATES", {}),
            (world, "WORLD", world.World()),
        ):
            p = patch.object(obj, attr, val)
            p.start()
            self.addCleanup(p.stop)
        self.room = world.Room(888888, "A quiet road", "A secluded roadway.", safe=False)
        world.WORLD.rooms[self.room.vnum] = self.room
        self.saved = patch.object(storage, "save_player")
        self.saved.start()
        self.addCleanup(self.saved.stop)
        self.growth = patch.object(combat, "grow_skill_from_usage")
        self.growth.start()
        self.addCleanup(self.growth.stop)
        self.imm = patch.object(combat, "is_immortal_immune_to_defeat", return_value=False)
        self.imm.start()
        self.addCleanup(self.imm.stop)
        tags._loaded_path = None
        tags._records = {}
        tags.register_items()

    def player(self, name="Maker", klass="bukijutsu", level=25, org="anbu"):
        p = Player(name, name, primary_class=klass, level=level)
        p.room_vnum = self.room.vnum
        p.pvp_organization = org
        p.maximum_chakra = p.chakra = 50000
        p.maximum_stamina = p.stamina = 50000
        p.maximum_health = p.health = 5000
        p.learned_skills = []
        p.practice_gate_enabled = True
        if klass == "bukijutsu" and level >= 10:
            leveling.sync_universal_skills(p)
            skill_training.mark_practiced(p, tags.SKILL_NAME)
        out = []
        return p, NS(player=p, send=out.append), out

    def test_old_scroll_ids_and_buki_auto_unlock_at_ten(self):
        self.assertEqual(jutsu_scroll_catalog.vnum_for("kai"), 31760)
        self.assertEqual(jutsu_scroll_catalog.vnum_for(tags.SKILL_KEY), 31761)
        self.assertEqual(data_jutsu.JUTSU[tags.SKILL_KEY]["level_requirement"], 10)
        self.assertIn(tags.SKILL_KEY, data_jutsu.jutsu_for_class_at_level("bukijutsu", 10))
        self.assertNotIn(tags.SKILL_KEY, data_jutsu.jutsu_for_class_at_level("taijutsu", 10))
        buki, _session, _out = self.player(level=10)
        self.assertIn(tags.SKILL_NAME, buki.learned_skills)
        self.assertEqual(tags.TAGS["explosive"][2], 10)
        self.assertEqual(tags.TAGS["snare"][2], 10)

    def test_cross_class_scroll_rejects_24_and_teaches_at_25(self):
        jutsu_scroll_catalog.install(migrate_saved=False)
        p, session, logs = self.player(klass="taijutsu", level=24)
        scroll = jutsu_scroll_catalog.name_for(tags.SKILL_KEY)
        p.inventory.append(scroll)
        commands.cmd_read(session, ["scroll", "of", "trap", "tag", "placement"])
        self.assertIn(scroll, p.inventory)
        self.assertNotIn(tags.SKILL_NAME, p.learned_skills)
        self.assertIn("level 25", "\n".join(logs))
        p.level = 25
        commands.cmd_read(session, ["scroll", "of", "trap", "tag", "placement"])
        self.assertNotIn(scroll, p.inventory)
        self.assertIn(tags.SKILL_NAME, p.learned_skills)
        self.assertFalse(skill_training.needs_first_practice(p, tags.SKILL_NAME))
        self.assertTrue(combat._can_use_jutsu(p, data_jutsu.JUTSU[tags.SKILL_KEY], tags.SKILL_KEY))

    def test_place_consumes_tag_and_persists_across_loads(self):
        p, session, logs = self.player(level=10)
        p.inventory.append(tags.TAGS["explosive"][1])
        commands.cmd_trap(session, ["place", "explosive"])
        self.assertNotIn(tags.TAGS["explosive"][1], p.inventory)
        self.assertIn("conceal", "\n".join(logs))
        before = p.chakra
        self.assertLess(before, 50000)
        self.assertTrue(os.path.isfile(tags._path()))
        tags._loaded_path = None
        tags._records = {}
        tags.load()
        self.assertEqual(tags._records[str(self.room.vnum)][0]["type"], "explosive")
        # Placement cannot bypass global PvP-safe zones.
        self.room.safe = True
        p.cooldowns.clear()
        p.inventory.append(tags.TAGS["snare"][1])
        commands.cmd_trap(session, ["place", "snare"])
        self.assertIn(tags.TAGS["snare"][1], p.inventory)

    def test_enemy_enter_disarms_on_success_and_triggers_on_failure(self):
        setter, setter_session, _ = self.player(level=25)
        setter.inventory.append(tags.TAGS["snare"][1])
        tags.command(setter_session, ["snare"])
        enemy, enemy_session, out = self.player("Enemy", "taijutsu", 25, "root")
        enemy.learned_skills.append("Trap Disabling")
        enemy.skill_proficiencies["Trap Disabling"] = 100
        with patch.object(tags.random, "randint", return_value=1):
            tags.on_enter(enemy_session)
        self.assertIn("automatically disarm", "\n".join(out))
        self.assertNotIn("entangled", enemy.active_status_effects)
        self.assertFalse(tags._records.get(str(self.room.vnum)))
        setter.cooldowns.clear()
        setter.inventory.append(tags.TAGS["snare"][1])
        tags.command(setter_session, ["snare"])
        out.clear()
        with patch.object(tags.random, "randint", return_value=100):
            tags.on_enter(enemy_session)
        self.assertIn("fail to disarm", "\n".join(out))
        self.assertIn("entangled", enemy.active_status_effects)
        self.assertFalse(tags._records.get(str(self.room.vnum)))

    def test_same_org_and_owner_are_exempt_while_unaffiliated_players_trigger(self):
        setter, setter_session, _ = self.player()
        setter.inventory.append(tags.TAGS["flashbang"][1])
        tags.command(setter_session, ["flashbang"])
        same, same_session, _ = self.player("Ally", "taijutsu", 25, "anbu")
        tags.on_enter(same_session)
        self.assertTrue(tags._records.get(str(self.room.vnum)))
        tags.on_enter(setter_session)
        self.assertTrue(tags._records.get(str(self.room.vnum)))
        civilian, civilian_session, messages = self.player("Civilian", "taijutsu", 25, "")
        tags.on_enter(civilian_session)
        self.assertIn("trigger", " ".join(messages))
        self.assertFalse(tags._records.get(str(self.room.vnum)))

    def test_real_entry_hook_springs_tag_for_unaffiliated_player(self):
        import territory
        setter, setter_session, _ = self.player()
        setter.inventory.append(tags.TAGS["snare"][1])
        tags.command(setter_session, ["snare"])
        outsider, _unused, messages = self.player("Outsider", "taijutsu", 25, "")
        entry_session = NS(player=outsider, send=messages.append)
        with patch.object(commands, "WORLD", world.WORLD), \
             patch.object(territory, "check_trap_trigger", return_value=None):
            commands._fire_enter_triggers(entry_session)
        self.assertIn("trigger", " ".join(messages))
        self.assertIn("entangled", outsider.active_status_effects)

    def test_immortal_look_lists_all_hidden_tags_but_mortal_look_does_not(self):
        import territory
        owner, owner_session, _ = self.player()
        owner.inventory.append(tags.TAGS["fire"][1])
        tags.command(owner_session, ["fire"])
        watcher, _session, output = self.player("Watcher", "taijutsu", 25, "")
        staff = NS(player=watcher, account=NS(staff_level="immortal"),
                   active_sessions=lambda: [], send=output.append)
        with patch.object(commands, "WORLD", world.WORLD), \
             patch.object(territory, "trap_at", return_value=None):
            commands.cmd_look(staff, [])
            self.assertIn("[IMM TRAP]", " ".join(output))
            self.assertIn("Fire Burst Tag", " ".join(output))
            self.assertIn("Owner: Maker", " ".join(output))
            output.clear()
            staff.account.staff_level = "player"
            commands.cmd_look(staff, [])
            self.assertNotIn("[IMM TRAP]", " ".join(output))
        self.assertTrue(tags._records.get(str(self.room.vnum)))


    def test_all_effect_types_and_existing_consumables(self):
        self.assertEqual(set(range(80, 89)),
                         {r[0] for r in tags.TAGS.values()})
        for key in (*tags.TAGS, *tags.EXISTING):
            with self.subTest(tag=key):
                p, session, messages = self.player("Target", "taijutsu", 250, "root")
                tags._trigger(session, {"type": key, "owner": "Maker"})
                self.assertTrue(messages)
                self.assertGreaterEqual(p.health, 1)

    def test_builder_collision_preserved(self):
        occupied = olc.default_object(80, "Builder Artifact")
        olc.OBJECT_TEMPLATES[80] = occupied
        summary = tags.register_items()
        self.assertIn(80, summary["collisions"])
        self.assertIs(olc.OBJECT_TEMPLATES[80], occupied)


if __name__ == "__main__":
    unittest.main()
