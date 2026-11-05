"""An extra, per-run access code for internet previews; not staff authentication."""
import hashlib
import hmac
import html
import secrets
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs,urlparse

from restaurant_profile import PROFILE


def safe_next(value):
    if not isinstance(value,str) or len(value)>2048 or not value.startswith('/') or value.startswith('//'):
        return '/'
    if '\\' in value or any(ord(c)<32 for c in value):return '/'
    parsed=urlparse(value)
    return value if not parsed.scheme and not parsed.netloc else '/'


class PreviewAccess:
    def __init__(self,origin,code,clock=None):
        self.origin=origin
        self.code_hash=hashlib.sha256(code.encode()).digest()
        self.clock=clock or time.monotonic
        self.tokens={};self.attempts={}

    def authenticated(self,handler):
        cookie=SimpleCookie()
        try:cookie.load(handler.headers.get('Cookie',''))
        except Exception:return False
        token=cookie['sa_preview'].value if 'sa_preview' in cookie else ''
        return self.tokens.get(token,0)>self.clock()

    def page(self,next_path='/',error=''):
        return f'''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>เปิดลิงก์ทดสอบ • {html.escape(PROFILE['short_name'])}</title>
        <style>body{{margin:0;padding:50px 20px;background:#f5f6f2;color:#233b34;font:16px Tahoma,sans-serif;line-height:1.7}}main{{max-width:440px;margin:30px auto;background:white;border:1px solid #dfe5dd;border-radius:16px;padding:28px}}h1{{font-size:25px}}label{{display:block;margin:22px 0 8px}}input,button{{font:inherit;box-sizing:border-box;width:100%;border-radius:8px;padding:12px}}input{{border:1px solid #bbc9bd}}button{{background:#205b46;color:white;border:0;margin-top:18px;cursor:pointer}}.hint{{font-size:14px;color:#718275}}.error{{color:#9a402a;background:#fcedeb;padding:10px;border-radius:8px}}</style>
        <main><p class="hint">ลิงก์ทดสอบจากภายนอก</p><h1>{html.escape(PROFILE['name'])}</h1><p>ใส่รหัสเปิดลิงก์ที่เจ้าของส่งให้ ก่อนเข้าใช้งานระบบทดสอบ</p>{f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ''}
        <form action="/preview/unlock" method="post"><input type="hidden" name="next" value="{html.escape(safe_next(next_path),quote=True)}"><label for="access-code">รหัสเปิดลิงก์ทดสอบ</label><input id="access-code" name="access_code" type="password" required maxlength="100" autocomplete="off"><button type="submit">เปิดระบบทดสอบ</button></form><p class="hint">บัญชีเจ้าของร้านและพนักงานใช้เข้าสู่ระบบในขั้นถัดไป ลิงก์นี้ทำงานขณะเครื่องเจ้าของเปิดโปรแกรมค้างไว้</p></main></html>'''

    def check(self,handler):
        """Return True to continue to the restaurant; otherwise respond here."""
        if handler.command=='POST' and handler.path=='/preview/unlock':
            if handler.headers.get('Origin')!=self.origin:
                handler.send(403,{'error':'คำขอต้องมาจากหน้าลิงก์ทดสอบนี้'});return False
            if handler.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':
                handler.send(400,{'error':'รูปแบบข้อมูลไม่ถูกต้อง'});return False
            try:size=int(handler.headers.get('Content-Length','0'))
            except ValueError:size=0
            if not 0<size<=4096:
                handler.send(400,{'error':'ข้อมูลไม่ถูกต้อง'});return False
            values=parse_qs(handler.rfile.read(size).decode('utf-8',errors='replace'))
            # This listener binds only to loopback and receives traffic from cloudflared.
            ip=handler.headers.get('CF-Connecting-IP') or handler.client_address[0]
            now=self.clock();recent=[t for t in self.attempts.get(ip,[]) if now-t<60]
            self.attempts[ip]=recent
            next_path=safe_next(values.get('next',['/'])[0])
            if len(recent)>=15:
                handler.send(429,self.page(next_path,'ลองรหัสบ่อยเกินไป กรุณารอ 1 นาที'),'text/html; charset=utf-8',referrer_policy='same-origin');return False
            recent.append(now)
            code=values.get('access_code',[''])[0]
            if not hmac.compare_digest(hashlib.sha256(code.encode()).digest(),self.code_hash):
                handler.send(401,self.page(next_path,'รหัสเปิดลิงก์ไม่ถูกต้อง'),'text/html; charset=utf-8',referrer_policy='same-origin');return False
            self.tokens={k:v for k,v in self.tokens.items() if v>now}
            token=secrets.token_urlsafe(32);self.tokens[token]=now+43200
            handler.redirect(next_path,f'sa_preview={token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=43200')
            return False
        if self.authenticated(handler):return True
        if handler.command=='GET' and not handler.path.startswith('/api/'):
            # Native form POSTs can serialize Origin as null under no-referrer.
            # Keep same-origin form verification without sending referrers elsewhere.
            handler.send(200,self.page(handler.path),'text/html; charset=utf-8',referrer_policy='same-origin')
        else:handler.send(401,{'error':'กรุณาใส่รหัสเปิดลิงก์ทดสอบก่อน','preview_unlock_required':True})
        return False
