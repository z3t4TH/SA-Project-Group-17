"""Publish inspectable synthetic fixtures; never read a runtime database."""
import csv
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.presentation import _seed, DEFAULT_DATE, verify


def export(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='readable-demo-') as folder:
        source = Path(folder) / 'presentation.sqlite3'
        _seed(source, DEFAULT_DATE)
        with sqlite3.connect(source) as connection:
            # Preserve referenced user/job IDs, while removing authentication,
            # idempotency responses and embedded per-bill QR payloads.
            for table in ('Sessions', 'Requests', 'AuditLog'):
                connection.execute(f'DELETE FROM "{table}"')
            connection.execute("UPDATE Users SET password_hash='DISABLED_READ_ONLY_EXAMPLE'")
            connection.execute("UPDATE Orders SET session_token='EXAMPLE-NOT-A-VALID-QR-' || order_id")
            connection.execute("UPDATE PrintJobs SET payload='{}'")
            connection.commit()
            tables = [r[0] for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            counts = {}
            for table in tables:
                cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
                rows = cursor.fetchall()
                counts[table] = len(rows)
                with (destination / (table + '.csv')).open('w', encoding='utf-8', newline='') as stream:
                    writer = csv.writer(stream, lineterminator='\n')
                    writer.writerow([column[0] for column in cursor.description])
                    writer.writerows(rows)
            sql = '\n'.join(connection.iterdump())
            sql += '\nPRAGMA user_version=3;\nPRAGMA foreign_keys=ON;\n'
        # Test exactly the text that will be distributed, including all FKs and
        # business totals, rather than relying on the source database alone.
        restored = Path(folder) / 'restored.sqlite3'
        with sqlite3.connect(restored) as connection:
            connection.executescript(sql)
            assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        result = verify(restored)
        (destination / 'demo-readable.sql').write_text(
            '-- SYNTHETIC READ-ONLY EXAMPLE: not a runnable application database.\n' + sql,
            encoding='utf-8')
        (destination / 'manifest.json').write_text(json.dumps(dict(
            synthetic=True, date=DEFAULT_DATE, schema_version=3,
            tables=counts, integrity=result['integrity'], foreign_key_errors=0,
            notes='Authentication disabled; sessions, requests and audit omitted; QR tokens and print payloads replaced.'
        ), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return counts


if __name__ == '__main__':
    print(json.dumps(export(ROOT / 'data/readable'), ensure_ascii=False, indent=2))
