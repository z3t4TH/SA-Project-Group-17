import tempfile
import unittest
from pathlib import Path
from service import Restaurant
from database_tools import database_lock,backup_database


class DatabaseTools(unittest.TestCase):
    def test_backup_is_consistent_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.sqlite3';app=Restaurant(path,True);app.initialize()
            destination=Path(folder)/'saved.sqlite3';backup_database(path,destination)
            saved=Restaurant(destination,True)
            c=saved.connect()
            try:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM MenuItems').fetchone()[0],6)
                self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            finally:c.close()
            with self.assertRaises(SystemExit):backup_database(path,destination)

    def test_lock_prevents_simultaneous_reset_or_servers(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.sqlite3'
            with database_lock(path):
                with self.assertRaises(SystemExit):
                    with database_lock(path):pass
            with database_lock(path):pass
