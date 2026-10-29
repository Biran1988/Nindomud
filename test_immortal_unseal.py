"""Immortal unseal integration: permissions, online/offline holders, no duplicates."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import combat
import commands
import data_tailed_beasts
import immortal_unseal
import storage
import tailed_beasts
import world
import session as session_module
from models import Player


class ImmortalUnsealTests(unittest.TestCase):
    def setUp(self):
        self.room_id = 992995
        self.patches = [
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(combat, "MOB_TEMPLATES", {}),
            patch.object(world.WORLD, "rooms", {
                self.room_id: world.Room(self.room_id, "Wilds", "Open ground.")
            }),
            patch.object(session_module, "ACTIVE_SESSIONS", []),
            patch.object(storage, "all_players", return_value=[]),
            patch.object(storage, "save_player"),
            patch.object(commands, "_broadcast_globally"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        tailed_beasts.register_all_beast_templates(combat)
        self.output = []
        self.staff = NS(
            account=NS(staff_level="implementor"),
            player=Player("Staff", "Staff", room_vnum=self.room_id),
            send=self.output.append,
        )

    def holder(self, name, beast, *, online=False):
        p = Player(name, name, jinchuriki_beast_key=beast,
                   jinchuriki_mastery=85, tailed_beast_mode_active=True,
                   room_vnum=self.room_id)
        if online:
            session = NS(player=p, state=NS(name="PLAYING"),
                         send=Mock(), combat_target=None, pvp_target=None)
            session_module.ACTIVE_SESSIONS.append(session)
            return p, session
        storage.all_players.return_value.append(p)
        return p, None

    def call(self, *words):
        immortal_unseal.command(self.staff, list(words))
        return "\n".join(self.output)

    def test_permission_checks_before_loading_player_data(self):
        self.staff.account.staff_level = "player"
        self.assertIn("Only immortals", self.call("list"))
        storage.all_players.assert_not_called()
        self.assertIn("Only immortals", self.call("mob", "1"))
        self.assertFalse(combat.MOBS_BY_ROOM)

    def test_list_shows_online_and_offline_holders(self):
        self.holder("Offline", "kurama")
        self.holder("Online", "matatabi", online=True)
        text = self.call("list")
        self.assertIn("Kurama", text)
        self.assertIn("Matatabi", text)
        self.assertIn("Offline", text)
        self.assertIn("Online", text)
        self.assertEqual(len(combat.MOBS_BY_ROOM), 0)

    def test_free_online_holder_by_player_and_announce(self):
        holder, live = self.holder("Naruto", "kurama", online=True)
        text = self.call("Naruto")
        self.assertIn("Unsealed Kurama from Naruto", text)
        self.assertEqual(holder.jinchuriki_beast_key, None)
        self.assertEqual(holder.jinchuriki_mastery, 0)
        self.assertFalse(holder.tailed_beast_mode_active)
        storage.save_player.assert_called_once_with(holder)
        mob = combat.mobs_in_room(self.room_id)[0]
        self.assertEqual(mob.tailed_beast_key, "kurama")
        self.assertIn("Kurama", live.send.call_args.args[0])
        self.assertIn("Kurama", commands._broadcast_globally.call_args.args[0])

    def test_free_offline_holder_by_mob_name_or_number(self):
        holder, _ = self.holder("Offline", "shukaku")
        self.assertIn("Unsealed Shukaku", self.call("mob", "1"))
        self.assertIsNone(holder.jinchuriki_beast_key)
        self.assertEqual(combat.mobs_in_room(self.room_id)[0].tailed_beast_key, "shukaku")
        storage.save_player.assert_called_once_with(holder)

    def test_already_roaming_beast_prevents_extraction(self):
        holder, _ = self.holder("Host", "matatabi")
        self.call("mob", "2")
        self.assertIsNone(holder.jinchuriki_beast_key)
        other, _ = self.holder("Second", "kurama")
        self.output.clear()
        self.assertIn("already loose", self.call("mob", "9"))
        self.assertEqual(other.jinchuriki_beast_key, "kurama")
        self.assertEqual(len(combat.mobs_in_room(self.room_id)), 1)

    def test_invalid_targets_do_not_change_holder(self):
        holder, _ = self.holder("Host", "isobu")
        for words in (("mob", "10"), ("mob", "not-a-beast"),
                      ("person-with-no-seal",), ("mob",)):
            self.output.clear()
            self.call(*words)
            self.assertEqual(holder.jinchuriki_beast_key, "isobu")
        storage.save_player.assert_not_called()
        self.assertEqual(len(combat.mobs_in_room(self.room_id)), 0)

    def test_duplicate_sealed_owners_cannot_spawn_duplicate(self):
        self.holder("A", "saiken")
        self.holder("B", "saiken")
        self.assertIn("duplicate holders", self.call("mob", "6"))
        self.assertEqual(len(combat.mobs_in_room(self.room_id)), 0)

    def test_failed_spawn_does_not_strip_player(self):
        holder, _ = self.holder("Host", "matatabi")
        with patch.object(tailed_beasts, "release_beast", side_effect=ValueError("spawn failed")):
            self.assertIn("seal is unchanged", self.call("Host"))
        self.assertEqual(holder.jinchuriki_beast_key, "matatabi")
        storage.save_player.assert_not_called()

    def test_failed_save_rolls_back_mob_and_holder(self):
        holder, _ = self.holder("Host", "chomei")
        with patch.object(storage, "save_player", side_effect=OSError("disk full")):
            self.assertIn("seal remains intact", self.call("Host"))
        self.assertEqual(holder.jinchuriki_beast_key, "chomei")
        self.assertEqual(holder.jinchuriki_mastery, 85)
        self.assertTrue(holder.tailed_beast_mode_active)
        self.assertEqual(len(combat.mobs_in_room(self.room_id)), 0)

    def test_unseal_during_rampage_reverses_stats(self):
        holder, live = self.holder("Host", "gyuki", online=True)
        holder.maximum_health, holder.health = 150, 140
        holder.maximum_chakra, holder.chakra = 150, 145
        holder.maximum_stamina, holder.stamina = 150, 138
        holder.rampage_until = 9999999999
        live.combat_target = object()
        self.call("mob", "Gyuki")
        self.assertEqual(holder.maximum_health, 100)
        self.assertEqual(holder.maximum_chakra, 100)
        self.assertEqual(holder.maximum_stamina, 100)
        self.assertEqual(holder.rampage_until, 0)
        self.assertIsNone(live.combat_target)


if __name__ == "__main__":
    unittest.main()
