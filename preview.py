#!/usr/bin/env python3
"""Temporary HTTPS preview; customer pages are public, staff pages require login."""
import json
import os
import queue
import re
import subprocess
import shutil
import threading
import time
from pathlib import Path

from controllers.http_controller import make_handler,RestaurantHTTPServer
from database_tools import database_lock
from models.menu_catalog import install_menu_catalog
from config import ROOT
from models.restaurant import Restaurant


def make_preview_handler(app,public_url,local_port=None):
    """Public customer preview, retaining staff authentication and exact origin checks."""
    return make_handler(app,public_url,local_port=local_port)


def main():
    local_binary=ROOT/'.tools/cloudflared'
    binary=local_binary if local_binary.is_file() else shutil.which('cloudflared')
    if not binary:raise SystemExit('กรุณาติดตั้ง cloudflared ตาม docs/REMOTE_PREVIEW.md')
    app=Restaurant(ROOT/'data/demo.sqlite3',True)
    tunnel=None;servers=[]
    access_file=ROOT/'data/preview-access.json'
    with database_lock(app.path):
        app.initialize();install_menu_catalog(app)
        app.enable_readable_export()
        events=queue.Queue()
        try:
            # Expose the public customer listener; staff APIs still require account login.
            tunnel=subprocess.Popen([str(binary),'tunnel','--url','http://127.0.0.1:8001','--no-autoupdate','--protocol','http2'],
                                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            def read_logs():
                for line in tunnel.stdout:
                    if 'trycloudflare.com' in line:
                        match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',line)
                        if match:events.put(match.group(0))
                events.put(None)
            threading.Thread(target=read_logs,daemon=True).start()
            print('กำลังสร้างลิงก์ HTTPS ชั่วคราว…',flush=True)
            try:public_url=events.get(timeout=60)
            except queue.Empty:raise SystemExit('ยังสร้างลิงก์ไม่ได้ กรุณาตรวจอินเทอร์เน็ตแล้วลองใหม่')
            if not public_url:raise SystemExit('Cloudflare Tunnel ไม่สามารถสร้างลิงก์ได้')
            local=RestaurantHTTPServer(('127.0.0.1',8000),make_preview_handler(app,public_url,local_port=8000))
            servers.append(local)
            remote=RestaurantHTTPServer(('127.0.0.1',8001),make_preview_handler(app,public_url))
            servers.append(remote)
            for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
            fd=os.open(access_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'w') as f:
                json.dump(dict(url=public_url,access_mode='public-customer-pages',mode='demo',pid=os.getpid(),created_at=app.stamp()),f,ensure_ascii=False,indent=2)
            print(f'เปิดลิงก์ทดสอบแล้ว: {public_url}\nหน้าลูกค้าเปิดได้เลย ไม่ต้องใส่รหัสลิงก์ • หน้าร้านยังต้องล็อกอิน\nเครื่องนี้ยังใช้ http://127.0.0.1:8000 ได้\nหยุดด้วย Ctrl+C',flush=True)
            while tunnel.poll() is None:time.sleep(1)
            raise SystemExit('ลิงก์ภายนอกหยุดทำงานแล้ว เปิด python3 app.py --mode demo เพื่อใช้เฉพาะในเครื่อง')
        except KeyboardInterrupt:pass
        finally:
            for server in servers:server.shutdown();server.server_close()
            if tunnel and tunnel.poll() is None:
                tunnel.terminate()
                try:tunnel.wait(timeout=10)
                except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait()
            if access_file.exists():
                try:
                    data=json.loads(access_file.read_text());data['stopped_at']=app.stamp()
                    fd=os.open(access_file,os.O_WRONLY|os.O_TRUNC,0o600)
                    with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,indent=2)
                except (OSError,ValueError):pass


if __name__=='__main__':main()
