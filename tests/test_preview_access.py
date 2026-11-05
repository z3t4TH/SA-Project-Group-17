import http.client
import json
import secrets
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlencode

from app import make_handler
from preview_access import PreviewAccess,safe_next
from service import Restaurant


class Preview(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=Restaurant(Path(self.tmp.name)/'preview.sqlite3',True);self.app.initialize()
        self.origin='https://preview.example.test';self.code='test-only-preview-code'
        self.gate=PreviewAccess(self.origin,self.code)
        self.remote=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.app,self.origin,preview_access=self.gate))
        self.local=ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler)
        self.local.RequestHandlerClass=make_handler(self.app,self.origin,local_port=self.local.server_port)
        self.threads=[]
        for server in [self.remote,self.local]:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.threads.append(thread)

    def tearDown(self):
        for server in [self.remote,self.local]:server.shutdown();server.server_close()
        for thread in self.threads:thread.join()
        self.tmp.cleanup()

    def request(self,path='/',data=None,cookie=None,local=False,extra=None,form=False):
        server=self.local if local else self.remote
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        origin=f'http://127.0.0.1:{server.server_port}' if local else self.origin
        headers={'Host':origin.split('://')[1],'Origin':origin,'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json','X-SA-Request':'1','Idempotency-Key':secrets.token_hex(16)}
        if cookie:headers['Cookie']=cookie
        headers.update(extra or {})
        body=(urlencode(data) if form else json.dumps(data)) if data is not None else None
        conn.request('POST' if data is not None else 'GET',path,body,headers)
        r=conn.getresponse();content=r.read().decode();result=(r.status,dict(r.getheaders()),content)
        conn.close();return result

    def unlock(self,next='/'):
        status,headers,_=self.request('/preview/unlock',dict(access_code=self.code,next=next),form=True)
        self.assertEqual(status,303);return headers['Set-Cookie'].split(';')[0]

    def test_public_app_and_api_are_gated_without_leaking_access_code(self):
        status,headers,page=self.request('/book');self.assertEqual(status,200)
        self.assertEqual(headers['Referrer-Policy'],'same-origin')
        self.assertIn('รหัสเปิดลิงก์ทดสอบ',page);self.assertNotIn(self.code,page)
        self.assertNotIn('slot-container',page)
        self.assertEqual(self.request('/api/config')[0],401)
        self.assertEqual(self.request('/api/login',dict(username='owner',password='owner1234'))[0],401)

    def test_unlock_preserves_qr_path_and_uses_secure_cookie(self):
        next='/order/example-token?from=qr'
        status,headers,_=self.request('/preview/unlock',dict(access_code=self.code,next=next),form=True)
        self.assertEqual(status,303);self.assertEqual(headers['Location'],next)
        for flag in ['HttpOnly','Secure','SameSite=Strict']:self.assertIn(flag,headers['Set-Cookie'])
        cookie=headers['Set-Cookie'].split(';')[0]
        status,_,data=self.request('/api/config',cookie=cookie)
        self.assertEqual(status,200);self.assertEqual(json.loads(data)['base_url'],self.origin)

    def test_wrong_code_and_cross_origin_unlock_are_rejected(self):
        self.assertEqual(self.request('/preview/unlock',dict(access_code='wrong'),form=True)[0],401)
        self.assertEqual(self.request('/preview/unlock',dict(access_code=self.code),form=True,extra={'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request('/api/config',extra={'Host':'127.0.0.1:8000'})[0],403)

    def test_public_staff_login_requires_gate_and_sets_secure_cookie(self):
        cookie=self.unlock()
        status,headers,_=self.request('/api/login',dict(username='staff',password='staff1234'),cookie=cookie)
        self.assertEqual(status,200);self.assertIn('Secure',headers['Set-Cookie'])
        staff_cookie=headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('/api/state',cookie=staff_cookie)[0],401)
        status,_,state=self.request('/api/state',cookie=cookie+'; '+staff_cookie)
        self.assertEqual(status,200);self.assertNotIn('sales',json.loads(state))

    def test_local_url_remains_available_without_external_gate(self):
        self.assertEqual(self.request('/api/config',local=True)[0],200)
        status,headers,_=self.request('/api/login',dict(username='owner',password='owner1234'),local=True)
        self.assertEqual(status,200);self.assertNotIn('; Secure',headers['Set-Cookie'])
        self.assertEqual(self.request('/api/login',dict(username='owner',password='owner1234'),local=True,extra={'Origin':'https://evil.test'})[0],403)

    def test_preview_cookie_expiry_and_rate_limit(self):
        self.gate.clock=lambda:0
        cookie=self.unlock();self.assertEqual(self.request('/api/config',cookie=cookie)[0],200)
        self.gate.clock=lambda:43201
        self.assertEqual(self.request('/api/config',cookie=cookie)[0],401)
        for _ in range(15):self.assertEqual(self.request('/preview/unlock',dict(access_code='wrong'),form=True)[0],401)
        self.assertEqual(self.request('/preview/unlock',dict(access_code=self.code),form=True)[0],429)

    def test_redirects_cannot_leave_the_preview_site(self):
        for value in ['//evil.test','https://evil.test','/\\evil.test','/\nLocation: https://evil.test',None]:self.assertEqual(safe_next(value),'/')
        status,headers,_=self.request('/preview/unlock',dict(access_code=self.code,next='//evil.test'),form=True)
        self.assertEqual(status,303);self.assertEqual(headers['Location'],'/')


if __name__=='__main__':unittest.main(verbosity=2)
