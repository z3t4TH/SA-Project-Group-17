"""Untrusted HTTP inputs must produce controlled errors, never partial transactions."""
import http.client,json,secrets,tempfile,threading,unittest
from pathlib import Path
from datetime import datetime
from http.server import ThreadingHTTPServer
from models.restaurant import Restaurant,TZ
from app import make_handler
from controllers.http_controller import RestaurantHTTPServer

class HTTPEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.app=Restaurant(Path(cls.tmp.name)/'http-edge.sqlite3',True,lambda:datetime(2026,11,5,10,tzinfo=TZ));cls.app.initialize()
        cls.server=RestaurantHTTPServer(('127.0.0.1',0),http.server.BaseHTTPRequestHandler);cls.origin=f'http://127.0.0.1:{cls.server.server_port}';cls.server.RequestHandlerClass=make_handler(cls.app,cls.origin)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def setUp(self):
        self.server.RequestHandlerClass.login_attempts.clear()
    def request(self,path,body=None,headers=None,post=False):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10);h={'Origin':self.origin,'Content-Type':'application/json','X-SA-Request':'1','Idempotency-Key':secrets.token_hex(16)};h.update(headers or {})
        c.request('POST' if post else 'GET',path,body,h);r=c.getresponse();result=(r.status,dict(r.getheaders()),r.read());c.close();return result
    def test_malformed_json_and_utf8_are_bad_requests(self):
        for blob in [b'{',b'{"a":}',b'null',b'[]',b'1',b'"text"',b'\xff\xfe',b'['*10000+b']'*10000,b'{"x":'*70+b'0'+b'}'*70]:
            with self.subTest(blob=blob[:20]):self.assertEqual(self.request('/api/reserve',blob,post=True)[0],400)
    def test_invalid_integer_in_get_never_returns_internal_error(self):
        for query in ['%C2%B2','%E2%91%A0','9'*5000,'-1','0','21','1.5','true']:
            with self.subTest(query=query[:20]):self.assertEqual(self.request('/api/slots?guests='+query)[0],400)
    def test_body_limits_missing_idempotency_and_header_validation(self):
        valid=json.dumps(dict(name='x',phone='0000000000',guests=2,slot='2026-11-05T11:00:00+07:00')).encode()
        for headers,status in [({'Idempotency-Key':''},400),({'Idempotency-Key':'short'},400),({'Origin':''},403),({'X-SA-Request':''},403),({'Content-Type':'text/plain'},403),({'Content-Length':'bad'},400),({'Content-Length':'0'},413),({'Content-Length':'100001'},413)]:
            with self.subTest(headers=headers):self.assertEqual(self.request('/api/reserve',valid,headers,True)[0],status)
        self.assertEqual(self.request('/api/reserve',b' '*100001,post=True)[0],413)
    def test_path_traversal_and_private_files_are_not_exposed(self):
        for path in ['/data/demo.sqlite3','/data/demo-readable.sql','/migrations/001_initial.sql','/.env','/models/restaurant.py','/static/../app.py','/static/%2e%2e/app.py','/static/menu-images/../catalog.json']:
            with self.subTest(path=path):self.assertIn(self.request(path)[0],[400,404])
    def test_login_rate_limit_and_wrong_credentials(self):
        for n in range(15):self.assertEqual(self.request('/api/login',json.dumps({'username':'missing','password':'wrong'}).encode(),post=True)[0],401)
        self.assertEqual(self.request('/api/login',json.dumps({'username':'owner','password':'owner1234'}).encode(),post=True)[0],429)
        self.server.RequestHandlerClass.login_attempts.clear()
    def test_security_headers_on_error_responses_and_cookie_not_trusted(self):
        status,headers,body=self.request('/api/state',headers={'Cookie':'sa_session=not-a-session'})
        self.assertEqual(status,401);self.assertEqual(headers['Cache-Control'],'no-store');self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy']);self.assertNotIn(b'Traceback',body)

    def test_qr_utf8_boundary_and_svg_escaping(self):
        from urllib.parse import quote
        for text,status in [('x'*106,200),('x'*107,400),('ก'*35,200),('ก'*36,400)]:
            with self.subTest(bytes=len(text.encode())):self.assertEqual(self.request('/qr.svg?text='+quote(text))[0],status)
        status,_,body=self.request('/qr.svg?text='+quote('<script>alert(1)</script>'))
        self.assertEqual(status,200);self.assertNotIn(b'<script>',body);self.assertIn(b'&lt;script&gt;',body)
    def test_authenticated_invalid_dates_and_identifiers_are_controlled(self):
        status,h,_=self.request('/api/login',json.dumps(dict(username='owner',password='owner1234')).encode(),post=True)
        self.assertEqual(status,200);cookie={'Cookie':h['Set-Cookie'].split(';')[0]}
        for path in ['/api/state?date=2026-02-30','/print/report?date=2026-99-99','/api/bill?id=%C2%B2','/print/job?id=%E2%91%A0']:
            with self.subTest(path=path):self.assertEqual(self.request(path,headers=cookie)[0],400)
        for path in ['/api/bill?id=999999','/print/job?id=999999']:
            with self.subTest(path=path):self.assertEqual(self.request(path,headers=cookie)[0],404)

    def test_short_burst_of_parallel_reads_completes_without_connection_reset(self):
        import concurrent.futures
        paths=['/book','/api/config','/api/slots?guests=2','/static/menu-images/menu-032.jpg']
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            statuses=list(ex.map(lambda n:self.request(paths[n%len(paths)])[0],range(120)))
        self.assertEqual(statuses,[200]*120)
