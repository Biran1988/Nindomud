"""Connection visibility, persistent policies and real socket login enforcement."""
import asyncio
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import commands
import country_geo
import force_commands
import help_system
import network_bans as bans
import server
import session as session_module
import storage


def fake(name="Biran", rank="implementor", ip="8.8.8.8", country="US", state="PLAYING"):
    return NS(account=NS(name=name, staff_level=rank), player=NS(name=name),
              connection_ip=ip, connection_port=12345, connection_country=country,
              state=NS(name=state), send=Mock(), send_paginated=Mock(), request_close=Mock())


class NetworkBanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = patch.object(storage, "DATA_DIR", self.temp.name)
        self.directory.start()
        self.addCleanup(self.directory.stop)
        self.actor = fake()

    def output(self):
        return "\n".join(call.args[0] for call in self.actor.send.call_args_list)

    def test_permissions_registration_help_and_unforceable_commands(self):
        self.assertIs(commands.COMMANDS["ip"], bans.cmd_ip)
        self.assertIs(commands.COMMANDS["ban"], bans.cmd_ban)
        for verb in ("ip", "ban"):
            self.assertNotIn(verb, force_commands.SAFE_FORCE_VERBS)
            self.assertTrue(any(e["primary_keyword"] == verb for e in help_system.DEFAULT_HELP_ENTRIES))
        player = fake(rank="player")
        bans.cmd_ip(player, [])
        self.assertIn("Only immortals", player.send.call_args.args[0])
        for rank in ("player", "helper", "builder", "area leader"):
            actor = fake(rank=rank)
            bans.cmd_ban(actor, ["1.0.0.1"])
            self.assertIn("Only Administrators", actor.send.call_args.args[0])
        self.assertEqual(bans.load_rules(), [])

    def test_persistent_exact_subnet_mapped_ipv6_and_remove(self):
        with patch.object(session_module, "ACTIVE_SESSIONS", []):
            bans.cmd_ban(self.actor, ["203.0.113.7", "abuse"])
            bans.cmd_ban(self.actor, ["ip", "2001:db8::ab/48"])
            bans.cmd_ban(self.actor, ["ip", "198.51.100.123/24"])
        self.assertEqual(len(bans.load_rules()), 3)
        self.assertTrue(bans.blocked("203.0.113.7", None))
        self.assertTrue(bans.blocked("::ffff:203.0.113.7", None))
        self.assertFalse(bans.blocked("203.0.113.8", None))
        self.assertTrue(bans.blocked("198.51.100.255", None))
        self.assertFalse(bans.blocked("198.51.101.1", None))
        self.assertTrue(bans.blocked("2001:db8::dead", None))
        self.assertFalse(bans.blocked("2001:db9::dead", None))
        self.assertEqual(bans.network("::ffff:203.0.113.7/120"), bans.network("203.0.113.0/24"))
        self.assertEqual(json.loads(bans._path().read_text())["rules"][0]["reason"], "abuse")
        bans.cmd_ban(self.actor, ["remove", "203.0.113.7"])
        self.assertFalse(bans.blocked("203.0.113.7", None))

    def test_full_country_names_codes_and_mult_word_names(self):
        with patch.object(session_module, "ACTIVE_SESSIONS", []):
            bans.cmd_ban(self.actor, ["country", "aUsTrAlIa"])
            bans.cmd_ban(self.actor, ["country", "Nigeria"])
            bans.cmd_ban(self.actor, ["country", "United", "Kingdom"])
        self.assertEqual([r["value"] for r in bans.load_rules()], ["AU", "NG", "GB"])
        for ip in ("1.0.0.1", "105.112.0.1"):
            self.assertTrue(bans.blocked(ip, country_geo.lookup(ip)))
        self.assertFalse(bans.blocked("8.8.8.8", "US"))
        self.assertFalse(bans.blocked("127.0.0.1", None))
        bans.cmd_ban(self.actor, ["remove", "country", "au"])
        self.assertFalse(bans.blocked("1.0.0.1", "AU"))
        self.assertTrue(bans.blocked("105.112.0.1", "NG"))

    def test_self_lockout_duplicate_invalid_country_and_bad_ip(self):
        for args in (["8.8.8.8"], ["ip", "0.0.0.0/0"], ["country", "US"],
                     ["999.2.3.4"], ["country", "NotACountry"], ["remove"], ["country"]):
            bans.cmd_ban(self.actor, args)
        self.assertEqual(bans.load_rules(), [])
        with patch.object(session_module, "ACTIVE_SESSIONS", []):
            bans.cmd_ban(self.actor, ["1.0.0.1"])
            bans.cmd_ban(self.actor, ["1.0.0.1"])
        self.assertEqual(len(bans.load_rules()), 1)
        self.assertIn("already exists", self.output())

    def test_all_matching_characters_and_login_sessions_disconnected(self):
        targets = [fake("A", ip="1.0.0.1", country="AU"),
                   fake("B", ip="1.0.0.1", country="AU", state="EDITING"),
                   fake("C", ip="1.0.0.2", country="AU", state="NAME")]
        targets[2].player = None
        other = fake("Other", ip="105.112.0.1", country="NG")
        with patch.object(session_module, "ACTIVE_SESSIONS", [self.actor, *targets, other]), \
                patch.object(storage, "save_player") as save:
            bans.cmd_ban(self.actor, ["country", "AU"])
        for target in targets:
            target.request_close.assert_called_once()
        other.request_close.assert_not_called()
        self.actor.request_close.assert_not_called()
        self.assertEqual(save.call_count, 2)
        self.assertIn("Disconnected 3", self.output())

    def test_overlap_removal_does_not_override_remaining_rule(self):
        with patch.object(session_module, "ACTIVE_SESSIONS", []):
            bans.cmd_ban(self.actor, ["1.0.0.1"])
            bans.cmd_ban(self.actor, ["country", "AU"])
            bans.cmd_ban(self.actor, ["remove", "1.0.0.1"])
        self.assertTrue(bans.blocked("1.0.0.1", "AU"))

    def test_save_error_does_not_leave_banned_connections_online(self):
        targets = [fake("A", ip="1.0.0.1", country="AU"),
                   fake("B", ip="1.0.0.2", country="AU")]
        with patch.object(session_module, "ACTIVE_SESSIONS", targets), \
                patch.object(storage, "save_player", side_effect=OSError("full disk")), \
                self.assertLogs("network_bans", level="ERROR"):
            bans.cmd_ban(self.actor, ["country", "AU"])
        self.assertTrue(bans.blocked("1.0.0.1", "AU"))
        for target in targets:
            target.request_close.assert_called_once()

    def test_write_failure_keeps_policy_and_players_connected(self):
        target = fake(ip="1.0.0.1", country="AU")
        with patch.object(session_module, "ACTIVE_SESSIONS", [target]), \
                patch.object(bans.os, "replace", side_effect=OSError("read only")):
            bans.cmd_ban(self.actor, ["country", "AU"])
        self.assertEqual(bans.load_rules(), [])
        target.request_close.assert_not_called()
        self.assertIn("Ban not changed", self.output())

    def test_ip_visibility_every_state_filter_and_no_passwords(self):
        target = fake("Naruto", ip="1.0.0.1", country="AU", state="EDITING")
        login = fake(ip="105.112.0.1", country="NG", state="PASSWORD")
        login.player = None
        with patch.object(session_module, "ACTIVE_SESSIONS", [target, login]):
            bans.cmd_ip(self.actor, [])
            rows = "\n".join(self.actor.send_paginated.call_args.args[0])
            self.assertIn("Naruto", rows)
            self.assertIn("[logging in]", rows)
            self.assertIn("1.0.0.1", rows)
            self.assertIn("Nigeria (NG)", rows)
            bans.cmd_ip(self.actor, ["naruto"])
            self.assertEqual(len(self.actor.send_paginated.call_args.args[0]), 1)

    def test_bad_policy_never_becomes_an_empty_ban_list(self):
        bans._path().write_text("{broken")
        with self.assertRaises(ValueError):
            bans.load_rules()
        bans.cmd_ban(self.actor, ["1.0.0.1"])
        self.assertEqual(bans._path().read_text(), "{broken")

    def test_offline_lookup_both_families_and_invalid_database(self):
        self.assertEqual(country_geo.lookup("1.0.0.1"), "AU")
        self.assertEqual(country_geo.lookup("::ffff:1.0.0.1"), "AU")
        self.assertEqual(country_geo.lookup("105.112.0.1"), "NG")
        self.assertIsNotNone(country_geo.lookup("2606:4700:4700::1111"))
        self.assertIsNone(country_geo.lookup("127.0.0.1"))
        self.assertIsNone(country_geo.lookup("::1"))
        for text in ("1.0.0.0,1.0.0.255,AU\n", "1.0.0.255,1.0.0.0,AU\n"):
            with self.assertRaises(ValueError):
                country_geo.parse_database(gzip.compress(text.encode()))


class SocketBanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(storage, "DATA_DIR", self.temp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        country_geo.load()
        self.listener = await asyncio.start_server(server.handle_connection, "127.0.0.1", 0)
        self.port = self.listener.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.listener.close()
        await self.listener.wait_closed()

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.addCleanup(writer.close)
        return reader, writer

    async def test_ip_ban_rejects_before_any_session_or_login_greeting(self):
        bans.save_rules([{"kind": "ip", "value": "127.0.0.1/32"}])
        with patch.object(server, "Session") as constructor:
            reader, writer = await self.connect()
            message = await asyncio.wait_for(reader.read(), 2)
        self.assertEqual(message.decode(), bans.DENIED_MESSAGE)
        constructor.assert_not_called()

    async def test_country_ban_enforced_before_login(self):
        bans.save_rules([{"kind": "country", "value": "NG"}])
        with patch.object(country_geo, "lookup", return_value="NG"), \
                patch.object(server, "Session") as constructor:
            reader, writer = await self.connect()
            message = await asyncio.wait_for(reader.read(), 2)
        self.assertIn(b"Access denied", message)
        constructor.assert_not_called()

    async def test_corrupt_runtime_policy_refuses_connection(self):
        bans._path().write_text("garbage")
        reader, writer = await self.connect()
        message = await asyncio.wait_for(reader.read(), 2)
        self.assertIn(b"access checks unavailable", message)

    async def test_allowed_connection_tracks_actual_peer_and_remove_restores_login(self):
        bans.save_rules([])
        reader, writer = await self.connect()
        greeting = await asyncio.wait_for(reader.read(8192), 2)
        self.assertTrue(greeting)
        actual = next(s for s in session_module.ACTIVE_SESSIONS
                      if s.connection_port == writer.get_extra_info("sockname")[1])
        self.assertEqual(actual.connection_ip, "127.0.0.1")
        self.assertIsNone(actual.connection_country)
        actual.request_close()
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0)


if __name__ == "__main__":
    unittest.main()
