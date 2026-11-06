"""Local, sanitized SQL snapshots of committed runtime data."""
import csv
import json
import logging
import os
from pathlib import Path
import sqlite3
import tempfile
import threading


class ReadableExport:
    def __init__(self, source, destination):
        self.source = Path(source).resolve()
        self.destination = Path(destination).resolve()
        self.csv_directory = self.destination.with_suffix('')
        if self.source == self.destination:
            raise ValueError('SQL export must not overwrite the database')
        self.lock = threading.Lock()
        self.last_error = None

    def refresh(self):
        # Serialize snapshot + replacement so an older export cannot replace a
        # newer one when HTTP requests finish on different threads.
        with self.lock:
            temporary = None
            staged = None
            try:
                with sqlite3.connect(self.source.as_uri() + '?mode=ro', uri=True) as source:
                    version = source.execute('PRAGMA user_version').fetchone()[0]
                    copy = sqlite3.connect(':memory:')
                    try:
                        source.backup(copy)
                        for table in ('Sessions', 'Requests', 'AuditLog'):
                            copy.execute(f'DELETE FROM "{table}"')
                        copy.execute("UPDATE Users SET password_hash='DISABLED_LOCAL_EXPORT'")
                        copy.execute("UPDATE Orders SET session_token='EXAMPLE-NOT-A-VALID-QR-' || order_id")
                        copy.execute("UPDATE PrintJobs SET payload='{}'")
                        copy.commit()
                        self.csv_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                        staged = tempfile.TemporaryDirectory(dir=self.csv_directory, prefix='.export-')
                        counts = {}
                        tables = [r[0] for r in copy.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
                        for table in tables:
                            cursor = copy.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
                            records = cursor.fetchall()
                            counts[table] = len(records)
                            path = Path(staged.name) / (table + '.csv')
                            with path.open('w', encoding='utf-8', newline='') as stream:
                                writer = csv.writer(stream, lineterminator='\n')
                                writer.writerow([field[0] for field in cursor.description])
                                writer.writerows(records)
                            path.chmod(0o600)
                        manifest = Path(staged.name) / 'manifest.json'
                        manifest.write_text(json.dumps(dict(source=self.source.name, tables=counts,
                            local_runtime_snapshot=True, authentication_disabled=True), indent=2) + '\n')
                        manifest.chmod(0o600)
                        sql = '\n'.join(copy.iterdump())
                    finally:
                        copy.close()
                self.destination.parent.mkdir(parents=True, exist_ok=True)
                # mkstemp creates owner-only permissions. Atomic replace keeps
                # readers from seeing partially written SQL.
                descriptor, temporary = tempfile.mkstemp(dir=self.destination.parent, suffix='.sql.tmp')
                with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                    stream.write('-- LOCAL RUNTIME SNAPSHOT: contains customer data; do not publish.\n')
                    stream.write('-- Authentication disabled; QR tokens and print payloads replaced.\n')
                    stream.write(sql + f'\nPRAGMA user_version={version};\nPRAGMA foreign_keys=ON;\n')
                # Each file is replaced atomically. Readers needing a consistent
                # multi-table transaction should inspect the single SQL file.
                for path in Path(staged.name).iterdir():
                    os.replace(path, self.csv_directory / path.name)
                os.replace(temporary, self.destination)
                self.last_error = None
            except Exception as error:
                # The business transaction already committed. Never report it
                # as failed (which could prompt a duplicate payment/order).
                self.last_error = str(error)
                logging.exception('Readable SQL export failed: %s', self.destination)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
                if staged:
                    staged.cleanup()
