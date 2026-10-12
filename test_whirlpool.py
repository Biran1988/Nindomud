"""Unlisted creation, Uzumaki restriction, world integration and persistence."""
import os
import tempfile
import unittest
from unittest.mock import patch

import areas
import ascii_art
import combat
import commands
import content
import data_clans
import data_villages
import help_system
import kage
import missions
import olc
import reincarnation
import session as sessions
from models import Account
from session import Session, State
import storage
import territory
import world
import world_persistence


class WhirlpoolTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for item in (
            patch.object(storage, "DATA_DIR", tmp.name),
            patch.object(storage, "ACCOUNTS_DIR", os.path.join(tmp.name, "accounts")),
            patch.object(storage, "PLAYERS_DIR", os.path.join(tmp.name, "players")),
            patch.object(world.WORLD, "rooms", {}),
            patch.object(combat, "MOB_TEMPLATES", {}),
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(olc, "OBJECT_TEMPLATES", {}),
            patch.object(sessions, "ACTIVE_SESSIONS", []),
        ):
            item.start()
            self.addCleanup(item.stop)

    def session(self):
        out = []
        s = Session(out.append, lambda: None)
        s.account = Account(name="Explorer", salt_hex="salt", hash_hex="hash")
        s._pending_name = "Explorer"
        s.state = State.CHARGEN_VILLAGE
        out.clear()
        return s, out

    def test_absent_from_menu_banner_help_and_invalid_answer_reprompts(self):
        for text in (data_villages.village_names_display(), ascii_art.login_screen(),
                     "\n".join(e["body"] for e in help_system.DEFAULT_HELP_ENTRIES)):
            self.assertNotIn("whirlpool", text.lower())
            self.assertNotIn("uzushiogakure", text.lower())
        menu = data_villages.village_names_display()
        self.assertEqual(len(menu.splitlines()), 5)
        s, out = self.session()
        s._prompt_village_selection()
        s.handle_line("unknown")
        self.assertIs(s.state, State.CHARGEN_VILLAGE)
        self.assertNotIn("whirlpool", "\n".join(out).lower())

    def test_hidden_keyword_case_and_whitespace_advance_to_class(self):
        content.populate()
        s, out = self.session()
        s.handle_line("  WhIrLpOoL  ")
        self.assertEqual(s._pending_village, "whirlpool")
        self.assertIs(s.state, State.CHARGEN_CLASS)

    def test_only_uzumaki_is_accepted_and_none_cannot_skip(self):
        content.populate()
        self.assertEqual(data_clans.clans_for_village("whirlpool"), ["uzumaki"])
        s, out = self.session()
        s.handle_line("whirlpool")
        s.handle_line("ninjutsu")
        self.assertEqual(data_clans.clan_names_display("whirlpool").count("&C"), 1)
        for line in ("none", "", "uchiha", "senju", "hyuga"):
            s.handle_line(line)
            self.assertIs(s.state, State.CHARGEN_CLAN)
        s.handle_line("uzumaki")
        self.assertIs(s.state, State.CHARGEN_LOADOUT)

    def test_actual_creation_world_login_and_reload(self):
        content.populate()
        s, out = self.session()
        with patch.object(reincarnation.secrets, "randbelow", return_value=1):
            for line in ("whirlpool", "ninjutsu", "uzumaki", "balanced", "male", "tan",
                         "black", "brown", "athletic", "confident", "yes"):
                s.handle_line(line)
        p = s.player
        self.assertIsNotNone(p)
        self.assertEqual((p.village, p.clan, p.room_vnum), ("whirlpool", "uzumaki", 80001))
        self.assertEqual(p.equipment["head"], "A Uzushio Headband")
        self.assertEqual(world.WORLD.get(p.room_vnum).name, "Uzushio Sealing Hall")
        self.assertTrue(world.WORLD.get(p.room_vnum).safe)
        self.assertEqual(olc.OBJECT_TEMPLATES[9006]["short_desc"], "A Uzushio Headband")
        loaded = storage.load_player(p.name)
        self.assertEqual((loaded.village, loaded.clan, loaded.room_vnum), ("whirlpool", "uzumaki", 80001))
        s._enter_world(loaded)
        self.assertIn("Uzushiogakure", "\n".join(out))
        self.assertIn("Uzushiogakure", "\n".join(commands.build_score_lines(loaded, "Explorer")))

    def test_uzumaki_creation_retains_exact_ashura_roll(self):
        with patch.object(reincarnation.secrets, "randbelow", return_value=0) as roll:
            p = Session._create_player("Reborn", "Reborn", "whirlpool", "taijutsu", "uzumaki")
        roll.assert_called_once_with(100)
        self.assertEqual((p.reincarnation, p.reincarnation_birth_clan), ("ashura", "uzumaki"))
        with self.assertRaises(ValueError):
            Session._create_player("Other", "Other", "whirlpool", "taijutsu", "uchiha")

    def test_area_added_to_existing_installation_without_replacing_builder_areas(self):
        areas.register_area("leaf", 1, 2500, "Builder")
        areas.register_area("forest-custom", 30000, 30100, "Builder")
        before = storage.load_areas()
        areas.ensure_single_village_areas()
        areas.ensure_hidden_village_areas()
        after = storage.load_areas()
        for key, entry in before.items():
            self.assertEqual(after[key], entry)
        self.assertEqual((after["whirlpool"]["vnum_start"], after["whirlpool"]["vnum_end"]), (80001, 82500))
        areas.ensure_hidden_village_areas()
        self.assertEqual(storage.load_areas(), after)

    def test_saved_rooms_keep_builder_edits_across_populate(self):
        content.populate()
        world.WORLD.get(1).description = "A builder's academy approach."
        world.WORLD.get(80001).description = "An edited sealing hall."
        world_persistence.save_world()
        content.populate()
        self.assertEqual(world.WORLD.get(1).description, "A builder's academy approach.")
        self.assertEqual(world.WORLD.get(80001).description, "An edited sealing hall.")

    def test_all_village_templates_headbands_and_mission_hooks_exist(self):
        content.populate()
        self.assertEqual(kage.kage_title("whirlpool"), "the Whirlpool Leader")
        self.assertEqual(len(missions.missions_for_village("whirlpool")), 2)
        for vnum in (5006, 5106, 5206, 5306, 5406, 6051, 6052, 6053, 6055, 6057):
            self.assertIn(vnum, combat.MOB_TEMPLATES)
        headbands = [p["short_desc"] for p in olc.OBJECT_TEMPLATES.values() if "Uzushio" in p["short_desc"]]
        self.assertEqual(len(headbands), 8)

    def test_new_trap_ids_do_not_clobber_exam_guardians_or_existing_village_ids(self):
        content.populate()
        import chunin_exam
        old_keys = ["leaf", "stone", "water", "cloud", "sand"]
        for index, village in enumerate(old_keys):
            for offset, trap in enumerate(territory.TRAP_TYPES):
                self.assertEqual(territory.trap_mob_vnum(village, trap), 6850 + index * 10 + offset)
        new_ids = {territory.trap_mob_vnum("whirlpool", trap) for trap in territory.TRAP_TYPES}
        self.assertFalse(new_ids & {chunin_exam.HEAVEN_GUARDIAN_VNUM, chunin_exam.EARTH_GUARDIAN_VNUM})
        self.assertTrue(all(vnum in combat.MOB_TEMPLATES for vnum in new_ids))
        self.assertIn("guardian", combat.MOB_TEMPLATES[chunin_exam.HEAVEN_GUARDIAN_VNUM]["short_desc"].lower())

    def test_deleted_or_conflicting_builder_reservation_is_never_recreated(self):
        storage.save_world_state({"deleted_areas": [{"name": "whirlpool", "vnum_start": 80001, "vnum_end": 82500}]})
        areas.ensure_hidden_village_areas()
        self.assertIsNone(areas.find_area("whirlpool"))
        storage.save_world_state({})
        areas.register_area("builder-island", 80001, 82500, "Builder")
        before = storage.load_areas()
        areas.ensure_hidden_village_areas()
        self.assertEqual(storage.load_areas(), before)
        content.populate()
        self.assertIsNone(world.WORLD.get(80001))
        s, out = self.session()
        s.handle_line("whirlpool")
        self.assertIs(s.state, State.CHARGEN_VILLAGE)
        self.assertNotIn("whirlpool", "\n".join(out).lower())


if __name__ == "__main__":
    unittest.main()
