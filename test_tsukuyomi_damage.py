"""Tsukuyomi damage balance: verify real commands, not only data constants."""
import tempfile
import unittest
from unittest.mock import patch

import commands
import data_mangekyo
import mangekyo
import world
from models import Account, Player
from session import Session, State


class TsukuyomiDamageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for name, value in (
            ("session.ACTIVE_SESSIONS", []),
            ("world.WORLD.rooms", {1: world.Room(1, "Starting room", "A room.")}),
            ("mangekyo._NEXT_TSUKUYOMI_ROOM_VNUM", None),
            ("storage.DATA_DIR", directory.name),
            ("storage.ACCOUNTS_DIR", directory.name + "/accounts"),
            ("storage.PLAYERS_DIR", directory.name + "/players"),
        ):
            p = patch(name, value)
            p.start()
            self.addCleanup(p.stop)
        self.caster = self.make_session("Caster")
        self.target = self.make_session("Target")
        mangekyo.open_tsukuyomi(self.caster, self.target, world)
        self.caster.player.tsukuyomi_actions_remaining = 10

    def make_session(self, name):
        s = Session(lambda _: None, lambda: None)
        s.account = Account(name, "", "")
        s.player = Player(name, name, room_vnum=1, health=20000,
                          maximum_health=20000, chakra=3000,
                          maximum_chakra=3000, stamina=3000,
                          maximum_stamina=3000)
        s.state = State.PLAYING
        return s

    def test_every_action_uses_new_damage_and_keeps_its_tradeoff(self):
        values = {
            "stab": (150, 250, 1, 0, 0),
            "impale": (300, 450, 2, 0, 0),
            "burn": (100, 200, 1, 110, 0),
            "crush": (400, 600, 1, 0, 0),
            "unmake": (0, 0, 1, 150, 150),
        }
        for action, (minimum, maximum, cost, stamina, chakra) in values.items():
            with self.subTest(action=action):
                spec = data_mangekyo.TSUKUYOMI_COMMANDS[action]
                self.assertEqual(spec["hp_damage"], (minimum, maximum))
                self.assertEqual(spec["countdown_cost"], cost)
                self.target.player.health = 20000
                self.target.player.stamina = 3000
                self.target.player.chakra = 3000
                self.caster.player.tsukuyomi_actions_remaining = 10
                # A maximum roll for Crush exceeds the 1-100 early-end roll.
                with patch("random.randint", return_value=maximum or 150):
                    commands._tsukuyomi_torture_action(self.caster, action)
                self.assertEqual(self.target.player.health, 20000 - maximum)
                self.assertEqual(self.target.player.stamina, 3000 - stamina)
                self.assertEqual(self.target.player.chakra, 3000 - chakra)
                self.assertEqual(self.caster.player.tsukuyomi_actions_remaining,
                                 10 - cost)
        self.assertEqual(data_mangekyo.TSUKUYOMI_COMMANDS["crush"]["early_end_chance_pct"], 25)

    def test_end_of_illusion_still_leaves_victim_alive_and_exhausted(self):
        self.caster.player.tsukuyomi_actions_remaining = 1
        with patch("random.randint", return_value=250):
            commands._tsukuyomi_torture_action(self.caster, "stab")
        self.assertEqual(self.target.player.health, 1000)  # 5% of 20,000
        self.assertEqual(self.target.player.stamina, 0)
        self.assertFalse(self.target.player.tsukuyomi_frozen)
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertIsNone(self.caster.player.tsukuyomi_active_target_name)


if __name__ == "__main__":
    unittest.main()
