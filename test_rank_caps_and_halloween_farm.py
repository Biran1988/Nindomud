"""Regression coverage for rank caps, Halloween candy, fast XP spawns and save all."""
import unittest
from datetime import date
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import commands
import force_commands
import halloween_event
import kage
import leveling
from models import Player


class RankCapTests(unittest.TestCase):
    def test_rank_caps_cover_every_ninja_rank(self):
        self.assertEqual(kage.RANK_LEVEL_CAPS, {
            "academy student": 10, "genin": 35, "chunin": 80,
            "special jonin": 135, "jonin": 200, "elite jonin": 250,
            "village elder": 250, "kage": 250,
        })
        self.assertEqual([level for level, _, _ in kage.PROMOTION_LADDER],
                         [80, 135, 200])

    def test_elite_jonin_cannot_automatically_become_village_elder(self):
        player = Player("ElderCandidate", "ElderCandidate",
                        village="leaf", village_rank="elite jonin",
                        level=250, completed_missions=list(range(1000)))
        result = kage.handle_promotion_request(player)
        self.assertEqual(player.village_rank, "elite jonin")
        self.assertIn("no further promotion", result.lower())

    def test_elite_jonin_can_reach_250_without_becoming_kage(self):
        player = Player("Experienced", "Experienced",
                        village_rank="elite jonin", level=249,
                        experience=leveling.cumulative_xp_for_level(249))
        self.assertEqual(leveling.rank_level_cap(player), 250)
        with patch.object(leveling.storage, "save_player"), patch.object(
                leveling.shinobi_notices, "announce_level"):
            messages = leveling.grant_experience(player, 10**12)
        self.assertEqual(player.level, 250)
        self.assertTrue(any("reached level 250" in msg for msg in messages))
        self.assertEqual(leveling.grant_experience(player, 10**12), [])

    def test_exp_cannot_cross_current_rank_cap(self):
        player = Player("CapTester", "CapTester", village_rank="genin",
                        level=35, experience=leveling.cumulative_xp_for_level(35))
        before = player.experience
        self.assertEqual(leveling.rank_level_cap(player), 35)
        self.assertEqual(leveling.grant_experience(player, 1_000_000), [])
        self.assertEqual((player.level, player.experience), (35, before))

    def test_after_promotion_leveling_resumes(self):
        player = Player("PromotionTester", "PromotionTester",
                        village_rank="genin", level=15,
                        experience=leveling.cumulative_xp_for_level(15))
        player.village_rank = "chunin"
        needed = leveling.xp_for_next_level(15) - player.experience
        with patch.object(leveling.storage, "save_player"), patch.object(
                leveling.shinobi_notices, "announce_level"):
            messages = leveling.grant_experience(player, needed)
        self.assertEqual(player.level, 16)
        self.assertTrue(any("reached level 16" in msg for msg in messages))

    def test_huge_xp_gain_stops_at_rank_cap_and_discards_overflow(self):
        player = Player("BigKillTester", "BigKillTester",
                        village_rank="chunin", level=79,
                        experience=leveling.cumulative_xp_for_level(79))
        with patch.object(leveling.storage, "save_player"), patch.object(
                leveling.shinobi_notices, "announce_level"):
            msgs = leveling.grant_experience(player, 10**12)
        self.assertEqual(player.level, 80)
        self.assertLess(player.experience, leveling.xp_for_next_level(80))
        self.assertTrue(any("Rank cap reached" in msg for msg in msgs))


class ForceSaveAllTests(unittest.TestCase):
    def test_admin_saves_ordinary_online_players_only(self):
        def sess(name, role):
            return NS(player=NS(name=name), account=NS(staff_level=role),
                      state=NS(name="PLAYING"), send=Mock(), send_prompt=Mock())
        admin, user1, user2, builder = (sess("Admin", "administrator"),
                                      sess("User1", "player"),
                                      sess("User2", "player"),
                                      sess("Builder", "builder"))
        peers = [admin, user1, user2, builder]
        admin.active_sessions = lambda: peers
        with patch.object(commands.storage, "save_player") as save, patch.object(
                commands.olc, "_log") as log:
            commands.cmd_force(admin, ["all", "save"])
        self.assertEqual(save.call_count, 2)
        self.assertEqual({x.args[0].name for x in save.call_args_list}, {"User1", "User2"})
        self.assertEqual(log.call_count, 2)
        self.assertIn("Saved 2 online", admin.send.call_args.args[0])

    def test_save_not_allowed_through_general_mpforce(self):
        self.assertIsNotNone(force_commands.validate_forced_command("save"))
        self.assertIsNotNone(force_commands.validate_forced_command("save world"))


class HalloweenFarmingTests(unittest.TestCase):
    def test_fast_mob_whitelist_does_not_include_boss(self):
        self.assertEqual(halloween_event.FAST_MOB_RESPAWN_SECONDS, 8)
        self.assertEqual(len(halloween_event.FAST_RESPAWN_VNUMS), 3)
        self.assertNotIn(halloween_event.BOSS_VNUM, halloween_event.FAST_RESPAWN_VNUMS)

    def test_candy_is_eat_consumable_not_use(self):
        player = Player("CandyTester", "CandyTester", level=20)
        player.inventory.append(halloween_event.CANDY_NAMES[0])
        player.maximum_health = 300
        player.health = 100
        session = NS(player=player, send=Mock())
        with patch("storage.save_player"):
            commands.cmd_eat(session, ["candy", "corn"])
        self.assertEqual(player.health, 200)
        self.assertNotIn(halloween_event.CANDY_NAMES[0], player.inventory)
        self.assertGreater(player.holiday_xp_boost_until, 0)


if __name__ == "__main__":
    unittest.main()
