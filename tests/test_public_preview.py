"""Exercise the actual public preview handler without starting a Cloudflare tunnel."""
import http.client,json,secrets,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from models.restaurant import Restaurant
from preview import make_preview_handler

class PublicPreview(unittest.TestCase):
    def test_customer_access_is_public_but_staff_authentication_remains(self):
        with tempfile.TemporaryDirectory() as temp:
            app=Restaurant(Path(temp)/'preview.sqlite3',True);app.initialize()
            origin='https://preview.example.test'
            server=ThreadingHTTPServer(('127.0.0.1',0),make_preview_handler(app,origin))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(path,data=None,cookie=None,extra=None):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                headers={'Host':'preview.example.test','Origin':origin,'Content-Type':'application/json','X-SA-Request':'1','Idempotency-Key':secrets.token_hex(16)}
                if cookie:headers['Cookie']=cookie
                headers.update(extra or {})
                c.request('POST' if data is not None else 'GET',path,json.dumps(data) if data is not None else None,headers)
                r=c.getresponse();result=(r.status,dict(r.getheaders()),r.read().decode());c.close();return result
            try:
                status,_,page=request('/book');self.assertEqual(status,200);self.assertNotIn('รหัสเปิดลิงก์ทดสอบ',page);self.assertIn('/static/app.js',page)
                status,_,config=request('/api/config');self.assertEqual(status,200);self.assertEqual(json.loads(config)['base_url'],origin)
                self.assertEqual(request('/api/state')[0],401)
                self.assertEqual(request('/api/config',extra={'Host':'evil.test'})[0],403)
                credentials=dict(username='owner',password='owner1234')
                self.assertEqual(request('/api/login',credentials,extra={'Origin':'https://evil.test'})[0],403)
                for username in ('owner','staff'):
                    status,headers,_=request('/api/login',dict(username=username,password=username+'1234'));self.assertEqual(status,200)
                    self.assertIn('Secure',headers['Set-Cookie']);cookie=headers['Set-Cookie'].split(';')[0]
                    status,_,state=request('/api/state',cookie=cookie);self.assertEqual(status,200)
                    if username=='staff':self.assertNotIn('sales',json.loads(state))
            finally:server.shutdown();server.server_close();thread.join()
