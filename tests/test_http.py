"""HTTP integration checks against an isolated temporary database."""
import http.client
import json
import tempfile
import threading
import unittest
import secrets
from pathlib import Path
from http.server import ThreadingHTTPServer

from app import make_handler
from service import Restaurant


class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.app=Restaurant(Path(cls.tmp.name)/'http.sqlite3',True);cls.app.initialize()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),http.server.BaseHTTPRequestHandler)
        cls.port=cls.server.server_port;cls.origin=f'http://127.0.0.1:{cls.port}'
        cls.server.RequestHandlerClass=make_handler(cls.app,cls.origin)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def request(self,path,body=None,cookie=None,extra=None,method=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        headers={'Origin':self.origin,'Content-Type':'application/json','X-SA-Request':'1','Idempotency-Key':secrets.token_hex(16)}
        if cookie:headers['Cookie']=cookie
        headers.update(extra or {})
        conn.request(method or ('POST' if body is not None else 'GET'),path,json.dumps(body).encode() if body is not None else None,headers)
        r=conn.getresponse();data=r.read();result=(r.status,dict(r.getheaders()),json.loads(data) if 'application/json' in r.getheader('Content-Type','') else data.decode());conn.close();return result

    def login(self,role='owner'):
        status,headers,_=self.request('/api/login',{'username':role,'password':role+'1234'})
        self.assertEqual(status,200);return headers['Set-Cookie'].split(';')[0]

    def test_public_and_authenticated_pages(self):
        for path in ['/','/book','/cancel','/login','/static/app.js','/static/style.css']:
            self.assertEqual(self.request(path)[0],200)
        self.assertEqual(self.request('/api/config')[2]['demo'],True)
        profile=self.request('/api/config')[2]['restaurant']
        self.assertEqual(profile['name'],'ร้านส้มตำ เมี่ยงคำ')
        self.assertEqual(profile['phone'],'075 421 787')
        self.assertEqual(self.request('/api/state')[0],401)
        self.assertEqual(self.request('/print/report')[0],401)
        self.assertEqual(self.request('/api/state',cookie=self.login())[0],200)

    def test_cookie_and_security_headers(self):
        status,headers,_=self.request('/api/login',{'username':'staff','password':'staff1234'})
        self.assertEqual(status,200)
        for item in ['HttpOnly','SameSite=Strict','Max-Age=43200']:self.assertIn(item,headers['Set-Cookie'])
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'],'no-store')

    def test_csrf_host_content_type_rejected(self):
        b={'username':'owner','password':'owner1234'}
        for header in [{'Origin':'http://evil.test'},{'Host':'evil.test'},{'Content-Type':'text/plain'},{'X-SA-Request':''}]:
            self.assertEqual(self.request('/api/login',b,extra=header)[0],403)

    def test_role_enforced_on_http_and_printing(self):
        cookie=self.login('staff')
        self.assertEqual(self.request('/api/settings',{'capacity':100},cookie)[0],403)
        self.assertEqual(self.request('/print/report',cookie=cookie)[0],403)
        self.assertNotIn('sales',self.request('/api/state',cookie=cookie)[2])

    def test_unknown_and_malformed_endpoints(self):
        self.assertEqual(self.request('/missing')[0],404)
        self.assertEqual(self.request('/api/guest?token=unknown')[0],404)
        self.assertEqual(self.request('/api/reserve',[])[0],400)
        self.assertEqual(self.request('/api/slots?guests=NaN')[0],400)
        self.assertEqual(self.request('/api/login',{'username':"' OR 1=1 --",'password':'bad'})[0],401)

    def test_order_payment_receipt_and_html_escaping(self):
        owner=self.login();staff=self.login('staff')
        status,_,o=self.request('/api/open_table',{'table_id':1},staff);self.assertEqual(status,200)
        note='<script>alert(1)</script>'
        status,_,order=self.request('/api/place_order',{'token':o['token'],'items':[{'menu_id':1,'quantity':1,'expected_price':6500,'note':note}]})
        self.assertEqual(status,200)
        printed=self.request('/print/job?id='+str(order['job_id']),cookie=staff)[2]
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',printed);self.assertNotIn(note,printed)
        data={'id':o['id'],'method':'MOCK_QR','expected_total':6500,'confirmed':True}
        status,_,pay=self.request('/api/pay',data,staff);self.assertEqual(status,200)
        status,_,receipt=self.request('/print/job?id='+str(pay['job_id']),cookie=staff)
        self.assertEqual(status,200);self.assertIn('65.00',receipt);self.assertIn('Mock QR',receipt)
        self.assertIn('ร้านส้มตำ เมี่ยงคำ',receipt)
        self.assertEqual(self.request('/api/guest?token='+o['token'])[0],404)
        self.assertEqual(self.request('/api/state',cookie=owner)[2]['sales']['total'],6500)


if __name__=='__main__':unittest.main(verbosity=2)
