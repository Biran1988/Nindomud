"""Regression checks: Forest of Death central tower, scrolls, and Chunin 1v1."""
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import chunin_exam as exam
import combat
import commands
import forest_of_death_grid as forest
import storage
import world
from models import Player


class ChuninTowerFinalTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("CandidateExam", "CandidateExam", village="leaf")
        self.player.village_rank = "genin"
        self.player.level = 15
        self.player.primary_class = "taijutsu"
        self.player.maximum_health = 220
        self.player.maximum_chakra = 200
        self.player.maximum_stamina = 210
        self.player.strength = 33
        self.player.room_vnum = exam.TOWER_VNUM
        self.player.in_chunin_exam = True
        self.player.inventory = [exam.HEAVEN_SCROLL]
        self.player.backpack_contents = {"0": [exam.HELL_SCROLL]}
        self.session = NS(player=self.player, combat_target=None, pvp_target=None,
                          send=Mock(), broadcast_room=Mock())
        self.rooms = {357: forest.build_rooms()[357], 670: forest.build_final_room()}
        self.patches = [
            patch.object(world.WORLD, "rooms", self.rooms),
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(combat, "MOB_TEMPLATES", {}),
            patch("session.ACTIVE_SESSIONS", [self.session]),
            patch("storage.save_player")
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        exam.ensure_proctor()

    def test_proctor_is_real_protected_mob(self):
        exam.ensure_proctor()
        mobs = [m for m in combat.mobs_in_room(357) if m.template_vnum == exam.EXAM_PROCTOR_VNUM]
        self.assertEqual(len(mobs), 1)
        self.assertTrue(combat.is_immortal_mob(mobs[0]))

    def test_scrolls_are_consumed_only_when_1v1_starts(self):
        self.player.backpack_contents.clear()
        self.assertFalse(exam.start_final_trial(self.session))
        self.assertEqual(self.player.room_vnum, 357)
        self.assertEqual(self.player.inventory, [exam.HEAVEN_SCROLL])
        self.player.backpack_contents = {"0": [exam.EARTH_SCROLL]}
        with patch.object(commands, "cmd_look"):
            commands.cmd_ask(self.session, ["proctor", "exam"])
        self.assertEqual(self.player.room_vnum, 670)
        self.assertFalse(exam.has_both_scrolls(self.player))
        opponent = self.session.combat_target
        self.assertEqual(opponent.chunin_exam_owner, self.player.name)
        self.assertEqual(opponent.room_vnum, 670)
        self.assertNotEqual(opponent.primary_class, self.player.primary_class)
        self.assertGreater(opponent.max_health, self.player.maximum_health)
        self.assertEqual(self.player.village_rank, "genin")
        self.assertFalse(world.WORLD.get(670).exits)

    def test_busy_chamber_does_not_take_scrolls(self):
        other = Player("AnotherExam", "AnotherExam", village="leaf")
        other.in_chunin_exam = True
        other.room_vnum = 670
        with patch("session.ACTIVE_SESSIONS", [self.session, NS(player=other)]):
            self.assertFalse(exam.start_final_trial(self.session))
        self.assertTrue(exam.has_both_scrolls(self.player))
        self.assertEqual(self.player.room_vnum, 357)

    def test_victory_promotes_and_forfeit_does_not(self):
        self.assertTrue(exam.start_final_trial(self.session))
        mirror = self.session.combat_target
        with patch("kage.announce_rank_up"):
            self.assertTrue(exam.finish_final_match(self.session, mirror))
        self.assertEqual(self.player.village_rank, "chunin")
        self.assertFalse(self.player.in_chunin_exam)
        self.assertNotIn(mirror, combat.mobs_in_room(670))
        self.assertNotEqual(self.player.room_vnum, 670)

    def test_final_room_patches_only_670_and_never_repeats(self):
        with tempfile.TemporaryDirectory() as td:
            with (patch.object(storage, "DATA_DIR", td),
                  patch.object(storage, "ACCOUNTS_DIR", os.path.join(td, "accounts")),
                  patch.object(storage, "PLAYERS_DIR", os.path.join(td, "players"))):
                original = {"rooms": {"44": {"name": "untouched"}, "670": {"name": "old"},
                                      "671": {"name": "untouched also"}},
                            "mobs": {"91": {"name": "untouched"}},
                            "items": {"92": {"name": "untouched"}}}
                storage.save_world_state(original)
                self.assertTrue(forest.install_final_room_once())
                saved = storage.load_world_state()
                self.assertEqual(saved["rooms"]["670"]["name"], "Forest of Death -- Final Trial Chamber")
                self.assertEqual(saved["rooms"]["44"], original["rooms"]["44"])
                self.assertEqual(saved["rooms"]["671"], original["rooms"]["671"])
                self.assertEqual(saved["mobs"], original["mobs"])
                self.assertEqual(saved["items"], original["items"])
                saved["rooms"]["670"]["name"] = "Builder edit"
                storage.save_world_state(saved)
                self.assertFalse(forest.install_final_room_once())
                self.assertEqual(storage.load_world_state()["rooms"]["670"]["name"], "Builder edit")


if __name__ == "__main__":
    unittest.main()
