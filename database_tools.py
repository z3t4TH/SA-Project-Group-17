"""Database backups and cooperative process lock for macOS/Linux local runs."""
import fcntl
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from datetime import datetime


@contextmanager
def database_lock(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with open(str(path)+'.lock','a') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('ฐานข้อมูลนี้กำลังใช้งาน กรุณาหยุดเซิร์ฟเวอร์เดิมก่อน')
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def backup_database(path,destination):
    require_path=Path(path)
    if not require_path.exists():raise SystemExit('ยังไม่มีฐานข้อมูลให้สำรอง')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise SystemExit('ไฟล์สำรองมีอยู่แล้ว จะไม่เขียนทับ')
    source=sqlite3.connect(f'file:{require_path}?mode=ro',uri=True)
    target=sqlite3.connect(destination)
    try:source.backup(target)
    finally:target.close();source.close()
    return destination


def timestamp():return datetime.now().strftime('%Y%m%d-%H%M%S-%f')
