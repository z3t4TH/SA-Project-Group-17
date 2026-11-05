#!/usr/bin/env python3
"""Backup either mode, or archive and reset only the demo database."""
import argparse
import os
from config import ROOT
from models.restaurant import Restaurant
from database_tools import database_lock,backup_database,timestamp


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['backup','reset-demo','seed-presentation','reset-presentation','verify-presentation'])
    p.add_argument('--mode',choices=['demo','live','presentation'],default=None)
    p.add_argument('--date',help='วันจำลอง YYYY-MM-DD ใช้เฉพาะ Presentation')
    args=p.parse_args()
    if args.action.endswith('presentation'):
        if args.mode not in (None,'presentation'):raise SystemExit('คำสั่ง Presentation ไม่สามารถใช้กับฐาน demo/live ได้')
        from models.presentation import prepare,verify,metadata,DEFAULT_DATE
        import json
        path=ROOT/'data/presentation.sqlite3'
        if args.action=='verify-presentation':result=verify(path)
        else:result=prepare(path,args.date or metadata(path).get('presentation_date',DEFAULT_DATE),args.action=='reset-presentation')
        print(json.dumps(result,ensure_ascii=False,indent=2));return
    args.mode=args.mode or 'demo'
    if args.date:raise SystemExit('--date ใช้ได้เฉพาะคำสั่ง Presentation')
    if args.action=='reset-demo' and args.mode!='demo':raise SystemExit('คำสั่งนี้รีเซ็ตได้เฉพาะข้อมูลสาธิต')
    path=ROOT/'data'/f'{args.mode}.sqlite3'
    if args.action=='backup':
        destination=ROOT/'data/backups'/f'{args.mode}-{timestamp()}.sqlite3'
        print('สำรองข้อมูลแล้ว:',backup_database(path,destination));return
    with database_lock(path):
        if path.exists():
            backup=ROOT/'data/backups'/f'demo-before-reset-{timestamp()}.sqlite3'
            backup_database(path,backup);print('เก็บข้อมูลสาธิตเดิมไว้:',backup)
            import sqlite3
            c=sqlite3.connect(path);c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close()
        fresh=ROOT/'data'/f'demo-new-{timestamp()}.sqlite3'
        Restaurant(fresh,True).initialize()
        os.replace(fresh,path)
        print('เริ่มฐานข้อมูลสาธิตชุดใหม่แล้ว เปิดโปรแกรมอีกครั้งได้')


if __name__=='__main__':main()
