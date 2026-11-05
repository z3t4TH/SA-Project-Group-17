"""MVC Controller: route HTTP, authenticate requests, call Models and render Views."""
import json
import logging
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from models.menu_images import image_manifest,allowed_files
from config import ROOT
from models.restaurant import Problem, require
from restaurant_profile import PROFILE
from views.documents import RestaurantView
import qr
from controllers.managers import CommandRouter


class RestaurantHTTPServer(ThreadingHTTPServer):
    """Queue short bursts from menu images and concurrent restaurant clients."""
    request_queue_size=64


class RestaurantController(BaseHTTPRequestHandler):
    server_version = 'SA-Restaurant/1.0'

    def log_message(self, fmt, *args):
        # Keep private QR tokens and query data out of request logs.
        logging.info('%s %s', self.command, self.path.split('?')[0].split('/order/')[0])

    def send(self, status, data, kind='application/json; charset=utf-8', cookie=None, referrer_policy='no-referrer'):
        if kind.startswith('application/json'):
            data = json.dumps(data, ensure_ascii=False).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', referrer_policy)
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(data)

    def current_user(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        return self.model.user(cookie['sa_session'].value) if 'sa_session' in cookie else None

    def validate_host(self):
        require(self.headers.get('Host') in self.allowed_hosts, 'Host ไม่ถูกต้อง กรุณาใช้ URL ที่โปรแกรมแสดง', 403)

    def request_origin(self):
        return self.base_url if self.headers.get('Host') == self.allowed_host else 'http://' + self.headers.get('Host', '')

    def redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header('Location', location)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()

    def fail(self, e):
        self.send(e.status, dict(error=e.message, **e.details))

    def do_GET(self):
        try:
            self.validate_host()
            if self.preview_access and (not self.preview_access.check(self)):
                return
            self.get()
        except Problem as e:
            self.fail(e)
        except (sqlite3.Error, ValueError, TypeError):
            logging.exception('GET failed')
            self.fail(Problem('ไม่สามารถอ่านข้อมูลได้ กรุณาลองใหม่', 500))

    def get(self):
        parsed = urlparse(self.path)
        p = parsed.path
        q = parse_qs(parsed.query)
        u = self.current_user()
        if p == '/api/config':
            return self.send(200, dict(demo=self.model.demo, today=self.model.today(), now=self.model.stamp(), user=u, base_url=self.base_url, restaurant=PROFILE,menu_images=image_manifest(),presentation=getattr(self.model,"presentation",None)))
        if p == '/api/slots':
            return self.send(200,dict(slots=self.application.booking.checkQuota(q.get('guests',['1'])[0])))
        if p == '/api/state':
            return self.send(200, self.application.reports.workspace(u, q.get('date', [None])[0]))
        if p == '/api/bill':
            return self.send(200, self.application.payment.getBillSummary(u, q.get('id', [''])[0]))
        if p == '/api/guest':
            return self.send(200, self.application.foodorder.loadActiveMenu(q.get('token', [''])[0]))
        if p == '/qr.svg':
            text=q.get('text',[''])[0]
            require(len(text.encode('utf-8'))<=106,'ข้อความ QR ยาวเกินขนาดที่รองรับ (106 ไบต์)')
            return self.send(200, qr.svg(text), 'image/svg+xml')
        if p == '/print/job':
            data = self.application.document.loadDocument(u, q.get('id', [''])[0])
            return self.send(200, self.view.render_print_job(data, self.base_url, self.model.demo), 'text/html; charset=utf-8')
        if p == '/print/report':
            data = self.application.reports.loadReport(u, q.get('date', [self.model.today()])[0])
            return self.send(200, self.view.render_report(data, self.model.demo), 'text/html; charset=utf-8')
        if p == '/image-credits':
            return self.send(200,(ROOT/'assets/menu/image-credits.html').read_bytes(),'text/html; charset=utf-8')
        if p.startswith('/static/menu-images/'):
            name=p.removeprefix('/static/menu-images/')
            if name not in allowed_files():raise Problem('ไม่พบภาพเมนู',404)
            kind='image/svg+xml' if name.endswith('.svg') else 'image/jpeg'
            return self.send(200,(ROOT/'assets/menu/images'/name).read_bytes(),kind)
        if p in ('/', '/app', '/book', '/cancel', '/login') or p.startswith('/order/'):
            return self.send(200, self.view.index_document(), 'text/html; charset=utf-8')
        files = {'/static/app.js': 'app.js', '/static/style.css': 'style.css', '/static/print.js': 'print.js', '/static/views.js': 'views.js'}
        if p in files:
            name = files[p]
            return self.send(200, (ROOT / 'static' / name).read_bytes(), ('text/javascript' if name.endswith('.js') else 'text/css') + '; charset=utf-8')
        raise Problem('ไม่พบหน้านี้', 404)

    def do_POST(self):
        try:
            self.validate_host()
            if self.preview_access and (not self.preview_access.check(self)):
                return
            require(self.headers.get('Origin') == self.request_origin(), 'คำขอต้องมาจากหน้าโปรแกรมนี้', 403)
            require(self.headers.get('Content-Type', '').split(';')[0] == 'application/json' and self.headers.get('X-SA-Request') == '1', 'รูปแบบคำขอไม่ถูกต้อง', 403)
            size = int(self.headers.get('Content-Length', '0'))
            require(0 < size <= 100000, 'ข้อมูลมีขนาดใหญ่เกินไป', 413)
            try:
                b = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeError, RecursionError):
                raise Problem('ข้อมูล JSON ไม่ถูกต้อง')
            # Bound nesting before hashing or routing untrusted JSON (no recursion).
            pending=[(b,0)]
            while pending:
                value,depth=pending.pop()
                require(depth<=64,'ข้อมูล JSON ซ้อนกันมากเกินไป')
                if isinstance(value,dict):pending.extend((v,depth+1) for v in value.values())
                elif isinstance(value,list):pending.extend((v,depth+1) for v in value)
            require(self.path.startswith('/api/'), 'ไม่พบคำสั่ง', 404)
            action = self.path[5:]
            if action == 'login':
                ip = self.client_address[0]
                now = time.monotonic()
                recent = [t for t in self.login_attempts.get(ip, []) if now - t < 60]
                self.login_attempts[ip] = recent
                require(len(recent) < 15, 'ลองเข้าสู่ระบบบ่อยเกินไป กรุณารอ 1 นาที', 429)
                recent.append(now)
            result = self.application.execute(action, b, self.current_user(), self.headers.get('Idempotency-Key'))
            cookie = None
            if action == 'login':
                token = result.pop('token')
                cookie = f'sa_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'
                if self.request_origin().startswith('https://'):
                    cookie += '; Secure'
                result = {'message': 'เข้าสู่ระบบแล้ว'}
            elif action == 'logout':
                cookie = 'sa_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
                if self.request_origin().startswith('https://'):
                    cookie += '; Secure'
            self.send(200, result, cookie=cookie)
        except Problem as e:
            self.fail(e)
        except sqlite3.IntegrityError:
            self.fail(Problem('ข้อมูลซ้ำหรือสถานะเปลี่ยนแล้ว กรุณาตรวจสอบอีกครั้ง', 409))
        except (ValueError, TypeError):
            self.fail(Problem('ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบช่องกรอก'))
        except Exception:
            logging.exception('POST failed')
            self.fail(Problem('บันทึกไม่สำเร็จ ระบบย้อนกลับรายการแล้ว กรุณาลองใหม่', 500))


def make_handler(app,base_url,local_port=None,preview_access=None):
    """Bind one controller type to a Model and origin for each server instance."""
    allowed_host=urlparse(base_url).netloc
    allowed_hosts={allowed_host}
    if local_port is not None:
        allowed_hosts.update({f'127.0.0.1:{local_port}',f'localhost:{local_port}'})
    return type('BoundRestaurantController',(RestaurantController,),dict(
        model=app,application=CommandRouter(app),view=RestaurantView(),base_url=base_url,allowed_host=allowed_host,
        allowed_hosts=allowed_hosts,preview_access=preview_access,login_attempts={},
    ))
