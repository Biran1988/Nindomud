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
        self.player.backpack_contents = {"0": [exam.EARTH_SCROLL]}
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

    def test_scrolls_accepted_then_hokage_speaks_before_shadow_appears(self):
        self.player.backpack_contents.clear()
        self.assertFalse(exam.start_final_trial(self.session))
        self.assertEqual(self.player.room_vnum, 357)
        self.assertEqual(self.player.inventory, [exam.HEAVEN_SCROLL])
        self.player.backpack_contents = {"0": [exam.EARTH_SCROLL]}
        with patch.object(commands, "cmd_look"):
            commands.cmd_ask(self.session, ["proctor", "exam"])
        self.assertEqual(self.player.room_vnum, 670)
        self.assertFalse(exam.has_both_scrolls(self.player))
        self.assertFalse(self.player.chunin_final_ready)
        self.assertIsNone(self.session.combat_target)
        self.assertEqual(combat.mobs_in_room(670), [])
        speech = "\n".join(str(call.args[0]) for call in self.session.send.call_args_list)
        self.assertIn("Third Hokage", speech)
        self.assertIn("Heaven", speech)
        self.assertIn("Earth", speech)
        self.assertIn("yes/no", speech)

        self.assertTrue(exam.handle_final_trial_answer(self.session, "yes"))
        self.assertTrue(self.player.chunin_final_ready)
        self.assertTrue(Player.from_dict(self.player.to_dict()).chunin_final_ready)
        opponent = exam.final_opponent(self.session)
        self.assertIsNotNone(opponent)
        self.assertEqual(opponent.chunin_exam_owner, self.player.name)
        self.assertEqual(opponent.room_vnum, 670)
        self.assertNotEqual(opponent.primary_class, self.player.primary_class)
        self.assertGreater(opponent.max_health, self.player.maximum_health)
        self.assertGreater(opponent.level, self.player.level)
        self.assertIsNone(self.session.combat_target)
        self.assertEqual(self.player.village_rank, "genin")
        self.assertFalse(world.WORLD.get(670).exits)

        # Consent reveals the shadow; only an actual attack begins combat.
        with patch.object(commands, "_wake_and_stand"), patch("room_actions.emit"):
            commands.cmd_attack(self.session, ["shadow"])
        self.assertIs(self.session.combat_target, opponent)

    def test_declining_keeps_the_room_empty_and_can_later_accept(self):
        self.assertFalse(exam.handle_final_trial_answer(self.session, "yes"))  # not in arena
        self.assertTrue(exam.start_final_trial(self.session))
        self.assertTrue(exam.handle_final_trial_answer(self.session, "no"))
        self.assertFalse(self.player.chunin_final_ready)
        self.assertIsNone(self.session.combat_target)
        self.assertEqual(combat.mobs_in_room(670), [])
        self.assertTrue(exam.handle_final_trial_answer(self.session, "ready"))
        self.assertTrue(exam.handle_final_trial_answer(self.session, "yes"))
        opponent = exam.final_opponent(self.session)
        self.assertIsNotNone(opponent)
        self.assertIs(exam.begin_final_match(self.session), opponent)
        self.assertIsNone(self.session.combat_target)

    def test_chunin_announcement_is_global_not_room_limited(self):
        import kage
        playing = NS(state=NS(name="PLAYING"), send=Mock(), send_prompt=Mock())
        disconnected = NS(state=NS(name="NAME"), send=Mock(), send_prompt=Mock())
        with patch("session.ACTIVE_SESSIONS", [playing, disconnected]):
            kage.announce_rank_up(self.player.name, "chunin")
        playing.send.assert_called_once_with(
            f"&Y{self.player.name} has been promoted to Chunin!&x")
        playing.send_prompt.assert_called_once()
        disconnected.send.assert_not_called()

    def test_old_hell_scroll_still_counts_as_earth(self):
        self.assertEqual(exam.SCROLLS, (exam.HEAVEN_SCROLL, exam.EARTH_SCROLL))
        self.player.backpack_contents = {"0": [exam.HELL_SCROLL]}
        self.assertTrue(exam.has_both_scrolls(self.player))
        self.assertTrue(exam.consume_both_scrolls(self.player))
        self.assertFalse(exam.has_both_scrolls(self.player))
        self.assertEqual(self.player.backpack_contents["0"], [])

    def test_busy_chamber_does_not_take_scrolls(self):
        other = Player("AnotherExam", "AnotherExam", village="leaf")
        other.in_chunin_exam = True
        other.room_vnum = 670
        with patch("session.ACTIVE_SESSIONS", [self.session, NS(player=other)]):
            self.assertFalse(exam.start_final_trial(self.session))
        self.assertTrue(exam.has_both_scrolls(self.player))
        self.assertEqual(self.player.room_vnum, 357)

    def test_victory_promotes_and_announces_globally(self):
        self.assertTrue(exam.start_final_trial(self.session))
        self.assertTrue(exam.handle_final_trial_answer(self.session, "yes"))
        mirror = exam.final_opponent(self.session)
        with patch("kage.announce_rank_up") as announce:
            self.assertTrue(exam.finish_final_match(self.session, mirror))
        announce.assert_called_once_with(self.player.name, "chunin")
        self.assertEqual(self.player.village_rank, "chunin")
        self.assertFalse(self.player.in_chunin_exam)
        self.assertFalse(self.player.chunin_final_ready)
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
