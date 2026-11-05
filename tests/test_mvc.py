"""Exercise the MVC boundaries through HTTP using isolated restaurant data."""
import http.client
import json
import secrets
import tempfile
import threading
import unittest
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

from controllers.http_controller import make_handler
from models.restaurant import Restaurant, TZ


class MVC(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.model=Restaurant(Path(self.temp.name)/'mvc.sqlite3',True,lambda:datetime(2026,11,4,11,tzinfo=TZ))
        self.model.initialize()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),http.server.BaseHTTPRequestHandler)
        self.origin=f'http://127.0.0.1:{self.server.server_port}'
        self.server.RequestHandlerClass=make_handler(self.model,self.origin)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()

    def request(self,path,body=None,cookie=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Origin':self.origin,'Content-Type':'application/json','X-SA-Request':'1','Idempotency-Key':secrets.token_hex(16)}
        if cookie:headers['Cookie']=cookie
        connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
        response=connection.getresponse();content=response.read().decode()
        result=(response.status,dict(response.getheaders()),json.loads(content) if 'application/json' in response.getheader('Content-Type','') else content)
        connection.close();return result

    def login(self,role):
        status,headers,_=self.request('/api/login',dict(username=role,password=role+'1234'))
        self.assertEqual(status,200);return headers['Set-Cookie'].split(';')[0]

    def test_all_document_views_and_closed_daily_report(self):
        owner=self.login('owner');staff=self.login('staff')
        status,_,queue=self.request('/api/queue_create',dict(name='ลูกค้าทดสอบ',guests=2),staff)
        self.assertEqual(status,200)
        status,_,html=self.request('/print/job?id='+str(queue['job_id']),cookie=staff)
        self.assertEqual(status,200);self.assertIn('Q001',html)
        self.assertEqual(self.request('/api/queue_cancel',dict(id=queue['id']),staff)[0],200)
        status,_,opened=self.request('/api/open_table',dict(table_id=1),staff);self.assertEqual(status,200)
        status,_,html=self.request('/print/job?id='+str(opened['job_id']),cookie=staff)
        self.assertEqual(status,200);self.assertIn(self.origin+'/order/'+opened['token'],html);self.assertIn('<svg',html)
        status,_,ordered=self.request('/api/place_order',dict(token=opened['token'],items=[dict(menu_id=1,quantity=2,expected_price=6500,note='<b>ไม่เผ็ด</b>')]))
        self.assertEqual(status,200)
        status,_,html=self.request('/print/job?id='+str(ordered['job_id']),cookie=staff)
        self.assertEqual(status,200);self.assertIn('&lt;b&gt;ไม่เผ็ด&lt;/b&gt;',html)
        status,_,paid=self.request('/api/pay',dict(id=opened['id'],expected_total=13000,method='CASH',received='150'),staff)
        self.assertEqual(status,200)
        status,_,html=self.request('/print/job?id='+str(paid['job_id']),cookie=staff)
        self.assertEqual(status,200);self.assertIn('130.00 บาท',html);self.assertIn('ทอน 20.00 บาท',html)
        status,_,html=self.request('/print/report?date=2026-11-04',cookie=owner)
        self.assertEqual(status,200);self.assertIn('ยังไม่ได้ปิดบัญชีวันนี้',html)
        status,_,_=self.request('/api/staff_save',dict(name='พนักงาน <ทดสอบ>',role='บริการ',rate='10',active=True),owner)
        self.assertEqual(status,200)
        data=self.request('/api/state',cookie=owner)[2]
        sid=next(s['staff_id'] for s in data['staff'] if s['name']=='พนักงาน <ทดสอบ>')
        status,_,_=self.request('/api/settle',dict(actual_cash='130',material='20',staff_ids=[str(sid)]),owner)
        self.assertEqual(status,200)
        status,_,html=self.request('/print/report?date=2026-11-04',cookie=owner)
        self.assertEqual(status,200)
        for fragment in ['รายงานผลประกอบการและจัดสรรเงิน','ส่วนที่ 1: 25.00 บาท','พนักงาน &lt;ทดสอบ&gt;','10.00 บาท']:
            self.assertIn(fragment,html)
        self.assertNotIn('<ทดสอบ>',html)
        self.assertEqual(self.request('/api/state',cookie=owner)[2]['sales']['total'],13000)

    def test_views_keep_authorization_and_server_templates_private(self):
        staff=self.login('staff')
        self.assertEqual(self.request('/print/job?id=1')[0],401)
        self.assertEqual(self.request('/print/report',cookie=staff)[0],403)
        self.assertEqual(self.request('/print/job?id=99999',cookie=staff)[0],404)
        for path in ['/views/templates/index.html','/models/restaurant.py','/controllers/http_controller.py','/static/../config.py']:
            self.assertEqual(self.request(path)[0],404)
        for path in ['/book','/login','/app','/order/test-token']:
            status,_,html=self.request(path);self.assertEqual(status,200);self.assertIn('/static/app.js',html);self.assertLess(html.index('/static/views.js'),html.index('/static/app.js'))
        status,headers,script=self.request('/static/views.js')
        self.assertEqual(status,200);self.assertIn('javascript',headers['Content-Type']);self.assertIn('class MobileOrderForm',script)
        self.assertEqual(len(self.request('/api/slots?guests=2')[2]['slots']),10)
