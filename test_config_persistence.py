"""Regression tests: CONFIG and STAFFCONFIG survive login, reboot and quit."""
import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import commands
from models import Player
import storage


class ConfigPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'data'
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (
            ('DATA_DIR', str(root)),
            ('ACCOUNTS_DIR', str(root / 'accounts')),
            ('PLAYERS_DIR', str(root / 'players')),
        ):
            self.stack.enter_context(patch.object(storage, name, value))
        self.player = Player('ConfigPersistTest', 'ConfigPersistTest', village='leaf', clan='nara', primary_class='taijutsu')
        self.session = SimpleNamespace(player=self.player, send=Mock(),
                                       account=SimpleNamespace(staff_level='implementor'))
        storage.save_player(self.player)

    def test_defaults_are_on_for_new_characters(self):
        p = Player('FreshPrefs', 'FreshPrefs')
        for name in (*commands.CONFIG_OPTIONS, *commands.STAFF_CONFIG_OPTIONS):
            self.assertTrue(getattr(p, name), name)

    def test_config_saved_immediately_for_all_options_and_login(self):
        for name in commands.CONFIG_OPTIONS:
            commands.cmd_config(self.session, [name, 'off'])
            self.assertFalse(getattr(storage.load_player(self.player.name), name), name)
        # Simulate replacing the entire in-memory player on login/restart.
        self.player = storage.load_player(self.player.name)
        for name in commands.CONFIG_OPTIONS:
            self.assertFalse(getattr(self.player, name), name)
        self.session.player = self.player
        commands.cmd_config(self.session, ['tips', 'on'])
        reloaded = storage.load_player(self.player.name)
        self.assertTrue(reloaded.tips)
        self.assertFalse(reloaded.auto_loot_gear)

    def test_staffconfig_saved_independently_for_all_options(self):
        with patch.object(commands.olc, '_require_builder', return_value=True):
            for name in commands.STAFF_CONFIG_OPTIONS:
                commands.cmd_staffconfig(self.session, [name, 'off'])
        reloaded = storage.load_player(self.player.name)
        for name in commands.STAFF_CONFIG_OPTIONS:
            self.assertFalse(getattr(reloaded, name), name)
        for name in commands.CONFIG_OPTIONS:
            self.assertTrue(getattr(reloaded, name), name)

    def test_failed_disk_save_reverts_live_setting(self):
        with patch.object(storage, 'save_player', side_effect=OSError('disk unavailable')):
            commands.cmd_config(self.session, ['tips', 'off'])
            self.assertTrue(self.player.tips)
            with patch.object(commands.olc, '_require_builder', return_value=True):
                commands.cmd_staffconfig(self.session, ['staff_notify_ideas', 'off'])
            self.assertTrue(self.player.staff_notify_ideas)
        self.assertIn('Unable to save', str(self.session.send.call_args_list))

    def test_quit_then_new_login_keeps_saved_config(self):
        commands.cmd_config(self.session, ['auto_sac_corpse', 'off'])
        with patch.object(commands.olc, '_require_builder', return_value=True):
            commands.cmd_staffconfig(self.session, ['staff_notify_reports', 'off'])
        self.session.request_close = Mock()
        commands.cmd_quit(self.session, [])
        self.session.request_close.assert_called_once()
        next_login = storage.load_player(self.player.name)
        self.assertFalse(next_login.auto_sac_corpse)
        self.assertFalse(next_login.staff_notify_reports)

    def test_failed_atomic_replace_keeps_last_valid_player_save(self):
        commands.cmd_config(self.session, ['tips', 'off'])
        original = Path(storage.player_path(self.player.name)).read_bytes()
        with patch.object(storage.os, 'replace', side_effect=OSError('disk full')):
            commands.cmd_config(self.session, ['tips', 'on'])
        self.assertEqual(Path(storage.player_path(self.player.name)).read_bytes(), original)
        self.assertFalse(self.player.tips)

    def test_reboot_does_not_override_previously_saved_off(self):
        commands.cmd_config(self.session, ['auto_loot_ryo', 'off'])
        with patch.object(commands.olc, '_require_builder', return_value=True):
            commands.cmd_staffconfig(self.session, ['staff_show_vnums', 'off'])
        import main
        # Exercise the real main.main startup routine without opening sockets
        # or touching other server data; it must not scan/reset player configs.
        with (patch('main.storage.ensure_dirs'), patch('main.content.populate'),
              patch('ui_palette.load'), patch('seasonal_events.sync_visitors'),
              patch('world.reconcile_apartment_ownership'),
              patch('currency_piles.restore_piles'), patch('help_system.seed_default_help'),
              patch('main.storage.account_exists', return_value=True),
              patch('main.asyncio.run'), patch('main.run_server', new=Mock(return_value=None))):
            main.main()
        reloaded = storage.load_player(self.player.name)
        self.assertFalse(reloaded.auto_loot_ryo)
        self.assertFalse(reloaded.staff_show_vnums)


if __name__ == '__main__':
    unittest.main()
