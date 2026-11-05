#!/usr/bin/env python3
"""Start the MVC restaurant application. Python 3.10+, standard library only."""
import argparse
import getpass
import logging
from urllib.parse import urlparse

from config import ROOT
from controllers.http_controller import make_handler,RestaurantHTTPServer
from models.restaurant import Problem, Restaurant, require
from models.menu_catalog import install_menu_catalog
from database_tools import database_lock
from restaurant_profile import PROFILE
# Kept for callers which imported these printable View helpers from app.py.
from views.documents import esc, baht, print_document


def main():
    parser=argparse.ArgumentParser(description='SA Restaurant local application')
    parser.add_argument('--mode',choices=['demo','live','presentation'],default='demo')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--base-url',help='Exact origin, e.g. http://192.168.1.5:8000 for a trusted LAN')
    parser.add_argument('--init-owner',action='store_true')
    args=parser.parse_args()
    base=(args.base_url or f'http://{args.host}:{args.port}').rstrip('/')
    require(urlparse(base).scheme=='http' and urlparse(base).path in ('','/') and len(base.encode())<=64,'base-url ต้องเป็น http origin ความยาวไม่เกิน 64 ไบต์')
    db_path=ROOT/'data'/f'{args.mode}.sqlite3'
    if args.mode=='presentation':
        if args.init_owner:raise SystemExit('Presentation ใช้บัญชีสาธิต ไม่ใช้ --init-owner')
        from models.presentation import prepare,presentation_clock,metadata,DEFAULT_DATE
        existing=metadata(db_path)
        prepare(db_path,existing.get('presentation_date',DEFAULT_DATE))
        application=Restaurant(db_path,True,presentation_clock(db_path))
        application.presentation=dict(date=existing.get('presentation_date',DEFAULT_DATE),simulated=True)
    else:
        application=Restaurant(db_path,args.mode=='demo')
    password=getpass.getpass('Owner password (at least 10 characters): ') if args.init_owner else None
    with database_lock(application.path):
        application.initialize(password)
        install_menu_catalog(application)
        try:server=RestaurantHTTPServer((args.host,args.port),make_handler(application,base))
        except OSError as e:raise SystemExit(f'เปิดเซิร์ฟเวอร์ไม่ได้: {e} ใช้ --port เพื่อเลือกพอร์ตอื่น')
        print(f'{PROFILE["name"]} • {"Presentation วันจำลอง" if args.mode=="presentation" else "ข้อมูลสาธิตสมมติ" if application.demo else "ข้อมูลจริง"}\nเปิด {base}\nหยุดด้วย Ctrl+C',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()


if __name__=='__main__':
    logging.basicConfig(level=logging.WARNING)
    try:main()
    except Problem as e:raise SystemExit(e.message)
