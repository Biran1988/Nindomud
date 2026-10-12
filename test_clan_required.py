"""Required village clan selection through chargen and final creation guards."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import commands
import data_clans
import data_villages
import help_system
from models import Player
from session import Session, State
import storage


class ClanRequiredTests(unittest.TestCase):
    def session(self, village="leaf"):
        output = []
        session = Session(output.append, lambda: None)
        session._pending_village = village
        session.state = State.CHARGEN_CLAN
        return session, output

    def test_prompt_describes_required_choice(self):
        s, out = self.session()
        s._handle_chargen_class("ninjutsu")
        text = "\n".join(out)
        self.assertIn("required", text)
        self.assertNotIn("optional", text)
        self.assertNotIn("skip", text)

    def test_none_empty_and_other_village_do_not_advance(self):
        for answer in ("none", "NONE", "", "   ", "no clan", "yotsuki", "not-a-clan"):
            with self.subTest(answer=answer):
                s, out = self.session()
                s.handle_line(answer)
                self.assertIs(s.state, State.CHARGEN_CLAN)
                self.assertEqual(s._pending_clan, "")
                self.assertIn("must choose", "\n".join(out))

    def test_every_village_clan_can_be_selected(self):
        for village in data_villages.VILLAGES:
            choices = data_clans.clans_for_village(village)
            self.assertTrue(choices, village)
            for clan in choices:
                s, out = self.session(village)
                s.handle_line("  " + clan.upper() + "  ")
                self.assertIs(s.state, State.CHARGEN_LOADOUT)
                self.assertEqual(s._pending_clan, clan)

    def test_invalid_final_choice_returns_to_clan_without_writes_or_rolls(self):
        s, out = self.session()
        s.state = State.CHARGEN_CONFIRM
        s._pending_clan = "none"
        with patch.object(storage, "save_account") as account, \
             patch.object(storage, "save_player") as player, \
             patch.object(Session, "_create_player") as factory:
            s.handle_line("yes")
        self.assertIs(s.state, State.CHARGEN_CLAN)
        account.assert_not_called()
        player.assert_not_called()
        factory.assert_not_called()

    def test_factory_cannot_make_clanless_or_foreign_clan(self):
        for clan in ("", "none", "yotsuki", "bogus"):
            with self.assertRaises(ValueError):
                Session._create_player("New", "New", "leaf", "ninjutsu", clan)
        with self.assertRaises(ValueError):
            Session._create_player("New", "New", "leaf", "ninjutsu")

    def test_factory_creates_valid_clans_for_all_villages(self):
        for village in data_villages.VILLAGES:
            clan = data_clans.clans_for_village(village)[0]
            p = Session._create_player("New", "New", village, "ninjutsu", clan)
            self.assertEqual(p.clan, clan)
            self.assertEqual(p.reincarnation_birth_clan, clan)

    def test_clan_switching_cannot_select_none_or_leave(self):
        p = Player("Existing", "Existing", clan="hyuga", village="leaf")
        s = NS(player=p, send=lambda line: None)
        for args in (["join", "none"], ["leave"], ["join", "yotsuki"]):
            commands.cmd_clan(s, args)
            self.assertEqual(p.clan, "hyuga")
        commands.cmd_clan(s, ["join", "nara"])
        self.assertEqual(p.clan, "nara")

    def test_legacy_clanless_save_can_load_and_choose_without_reroll(self):
        p = Player.from_dict(Player("Legacy", "Legacy", clan="none", village="leaf").to_dict())
        self.assertEqual(p.clan, "none")
        s = NS(player=p, send=lambda line: None)
        commands.cmd_clan(s, ["join", "hyuga"])
        self.assertEqual(p.clan, "hyuga")
        self.assertEqual(p.reincarnation, "")
        self.assertTrue(p.reincarnation_roll_complete)

    def test_help_matches_allowed_commands(self):
        page = next(e for e in help_system.DEFAULT_HELP_ENTRIES if e["primary_keyword"] == "clan")
        self.assertIn("required", page["body"])
        self.assertNotIn("clan leave", page["body"])
        self.assertNotIn("cosmetic only", page["body"])


if __name__ == "__main__":
    unittest.main()
