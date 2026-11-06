import concurrent.futures
import csv
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from config import TZ
from models.restaurant import Restaurant


class ReadableExportTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'demo.sqlite3'
        self.sql = self.path.with_name('demo-readable.sql')
        self.app = Restaurant(self.path, True, lambda: datetime(2026, 11, 6, 10, tzinfo=TZ))
        self.app.initialize()
        self.app.enable_readable_export()

    def tearDown(self):
        self.folder.cleanup()

    def reserve(self, index):
        return self.app.mutate('reserve', dict(name=f'ทดสอบ {index}', phone='0000000000', guests=1,
            slot='2026-11-06T11:00:00+07:00'), None, f'readable-test-{index}')

    def restore(self):
        connection = sqlite3.connect(':memory:')
        connection.executescript(self.sql.read_text())
        self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
        return connection

    def test_committed_reservation_updates_sql_and_keeps_source_auth(self):
        result = self.reserve(1)
        with self.restore() as restored:
            self.assertEqual(restored.execute('SELECT reservation_code FROM Reservations').fetchone()[0], result['code'])
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM Requests').fetchone()[0], 0)
            self.assertEqual(restored.execute('SELECT password_hash FROM Users LIMIT 1').fetchone()[0], 'DISABLED_LOCAL_EXPORT')
        with self.app.connect() as source:
            self.assertNotEqual(source.execute('SELECT password_hash FROM Users LIMIT 1').fetchone()[0], 'DISABLED_LOCAL_EXPORT')
        with (self.path.parent / 'demo-readable/Reservations.csv').open() as stream:
            records = list(csv.DictReader(stream))
        self.assertEqual(records[0]['reservation_code'], result['code'])
        self.assertEqual(len(list((self.path.parent / 'demo-readable').glob('*.csv'))), 20)
        self.assertEqual(self.sql.stat().st_mode & 0o777, 0o600)

    def test_rollback_leaves_snapshot_unchanged(self):
        before = self.sql.read_bytes()
        with self.assertRaises(RuntimeError):
            with self.app.transaction() as connection:
                connection.execute("UPDATE Tables SET capacity=3 WHERE table_id=1")
                raise RuntimeError('abort')
        self.assertEqual(self.sql.read_bytes(), before)

    def test_concurrent_commits_all_appear(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(self.reserve, range(8)))
        with self.restore() as restored:
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM Reservations').fetchone()[0], 8)
        with (self.path.parent / 'demo-readable/Reservations.csv').open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 8)

    def test_export_failure_does_not_report_committed_booking_as_failed(self):
        with patch('models.readable_export.os.replace', side_effect=OSError('disk failure')):
            with self.assertLogs(level='ERROR'):
                self.reserve(1)
        self.assertIsNotNone(self.app.readable_export.last_error)
        with self.app.connect() as source:
            self.assertEqual(source.execute('SELECT COUNT(*) FROM Reservations').fetchone()[0], 1)
        self.app.readable_export.refresh()
        self.assertIsNone(self.app.readable_export.last_error)
        with self.restore() as restored:
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM Reservations').fetchone()[0], 1)
        self.assertEqual(list(self.sql.parent.glob('*.sql.tmp')), [])

    def test_sessions_and_order_tokens_removed(self):
        self.app.mutate('login', dict(username='owner', password='owner1234'), None, 'readable-login-test')
        self.app.mutate('open_table', dict(table_id=1), {'user_id':1,'role':'OWNER'}, 'readable-open-test')
        with self.restore() as restored:
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM Sessions').fetchone()[0], 0)
            self.assertEqual(restored.execute('SELECT session_token FROM Orders').fetchone()[0], 'EXAMPLE-NOT-A-VALID-QR-1')
            self.assertEqual(restored.execute('SELECT DISTINCT payload FROM PrintJobs').fetchall(), [('{}',)])
