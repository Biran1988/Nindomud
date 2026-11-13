"""Failed writes must preserve the preceding JSON save and remove temp files."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import storage


class AtomicStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, path in (('DATA_DIR', self.root), ('ACCOUNTS_DIR', self.root / 'accounts'),
                           ('PLAYERS_DIR', self.root / 'players')):
            p = patch.object(storage, name, str(path))
            p.start()
            self.addCleanup(p.stop)
        storage.ensure_dirs()

    def test_all_shared_registries_preserve_previous_save_on_serialization_failure(self):
        registries = ['jackpots', 'bounties', 'territory', 'spawn_points',
                      'custom_templates', 'teams', 'chatlog', 'tips', 'auctions', 'areas']
        for name in registries:
            with self.subTest(registry=name):
                save = getattr(storage, 'save_' + name)
                load = getattr(storage, 'load_' + name)
                original = ['entry'] if name in ('chatlog', 'tips') else {'original': 42}
                save(original)
                with self.assertRaises(TypeError):
                    save({'not_json': object()})
                self.assertEqual(load(), original)
        self.assertEqual(list(self.root.rglob('*.tmp')), [])

    def test_account_serialization_failure_preserves_password_record(self):
        account = SimpleNamespace(name='Tester', to_dict=lambda: {'password_hash': 'original'})
        storage.save_account(account)
        account.to_dict = lambda: {'broken': object()}
        with self.assertRaises(TypeError):
            storage.save_account(account)
        saved = json.loads(Path(storage.account_path('Tester')).read_text())
        self.assertEqual(saved, {'password_hash': 'original'})

    def test_disk_flush_and_replace_failures_leave_previous_save(self):
        for operation in ('fsync', 'replace'):
            with self.subTest(operation=operation):
                storage.save_jackpots({'original': 42})
                with patch.object(storage.os, operation, side_effect=OSError('disk failure')):
                    with self.assertRaises(OSError):
                        storage.save_jackpots({'replacement': 99})
                self.assertEqual(storage.load_jackpots(), {'original': 42})
                self.assertEqual(list(self.root.rglob('*.tmp')), [])

    def test_successful_save_replaces_complete_document(self):
        storage.save_jackpots({'old': 42})
        storage.save_jackpots({'new': [1, 2, 3]})
        self.assertEqual(storage.load_jackpots(), {'new': [1, 2, 3]})
        self.assertEqual(list(self.root.rglob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
