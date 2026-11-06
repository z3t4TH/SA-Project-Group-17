"""Restaurant facade: lifecycle, queries, permissions and transaction boundaries."""
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime,timedelta
from pathlib import Path
from config import ROOT,TZ
from models.entities import Table,Payment,OrderItem
from restaurant_profile import accepts_bookings_on
from models.common import (Problem,require,money,integer,string,phone,password_hash,rows,one,rows_as_pairs,calendar_date)
from models.operations.auth import AuthOperations
from models.operations.reservations import ReservationOperations
from models.operations.queues import QueueOperations
from models.operations.orders import OrderOperations
from models.operations.payments import PaymentOperations
from models.operations.menu import MenuOperations
from models.operations.accounting import AccountingOperations
from models.operations.administration import AdministrationOperations
from models.operations.documents import DocumentOperations


class Restaurant:
    def __init__(self, path, demo=False, clock=None):
        self.path = str(path)
        self.demo = demo
        self.clock = clock or (lambda: datetime.now(TZ))
        self.readable_export = None
        self.operations={
            'auth':AuthOperations(self),
            'reservations':ReservationOperations(self),
            'queues':QueueOperations(self),
            'orders':OrderOperations(self),
            'payments':PaymentOperations(self),
            'menu':MenuOperations(self),
            'accounting':AccountingOperations(self),
            'administration':AdministrationOperations(self),
            'documents':DocumentOperations(self),
        }
        self._operation_routes={'login': ('auth', 'login'), 'logout': ('auth', 'logout'), 'reserve': ('reservations', 'reserve'), 'lookup': ('reservations', 'lookup'), 'cancel': ('reservations', 'cancel'), 'queue_create': ('queues', 'queue_create'), 'queue_call': ('queues', 'queue_call'), 'queue_skip': ('queues', 'queue_skip'), 'queue_seat': ('queues', 'queue_seat'), 'queue_cancel': ('queues', 'queue_cancel'), 'checkin': ('reservations', 'checkin'), 'no_show': ('reservations', 'no_show'), 'open_table': ('orders', 'open_table'), 'place_order': ('orders', 'place_order'), 'batch_status': ('orders', 'batch_status'), 'pay': ('payments', 'pay'), 'close_empty': ('payments', 'close_empty'), 'menu_save': ('menu', 'menu_save'), 'settle': ('accounting', 'settle'), 'print_status': ('documents', 'print_status'), 'settings': ('administration', 'settings'), 'table_save': ('administration', 'table_save'), 'staff_save': ('administration', 'staff_save'), 'user_save': ('administration', 'user_save')}


    def now(self):
        return self.clock().astimezone(TZ)

    def stamp(self):
        return self.now().isoformat(timespec='seconds')

    def today(self):
        return self.now().date().isoformat()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA busy_timeout=15000')
        return c

    @contextmanager
    def transaction(self):
        c = self.connect()
        committed = False
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
            committed = True
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()
        if committed and self.readable_export is not None:
            self.readable_export.refresh()

    def enable_readable_export(self, destination=None):
        from models.readable_export import ReadableExport
        self.readable_export = ReadableExport(
            self.path, destination or Path(self.path).with_name(Path(self.path).stem + '-readable.sql'))
        self.readable_export.refresh()

    def initialize(self, owner_password=None):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        c = self.connect()
        try:
            c.execute('PRAGMA journal_mode=WAL')
            version = c.execute('PRAGMA user_version').fetchone()[0]
            require(version <= 3, 'ฐานข้อมูลเวอร์ชันใหม่กว่าโปรแกรมนี้')
            if version == 0:
                c.executescript((ROOT/'migrations/001_initial.sql').read_text())
            if version < 2:
                c.executescript((ROOT/'migrations/002_menu_catalog.sql').read_text())
            if version < 3:
                try:
                    c.executescript('BEGIN IMMEDIATE;\n'+(ROOT/'migrations/003_order_batches.sql').read_text())
                    self._backfill_batches(c)
                    c.execute('PRAGMA user_version=3')
                    c.commit()
                except Exception:
                    c.rollback()
                    raise
        finally:
            c.close()
        with self.transaction() as c:
            mode = c.execute("SELECT value FROM Settings WHERE key='mode'").fetchone()
            require(mode is None or mode[0] == ('demo' if self.demo else 'live'), 'ห้ามเปิดฐานข้อมูลข้ามโหมดสาธิต/ข้อมูลจริง')
            c.execute("INSERT OR IGNORE INTO Settings VALUES('mode',?)", ('demo' if self.demo else 'live',))
            c.execute("INSERT OR IGNORE INTO Settings VALUES('slot_capacity','20')")
            if c.execute('SELECT COUNT(*) FROM Users').fetchone()[0] == 0:
                require(self.demo or (owner_password and len(owner_password) >= 10), 'เริ่มโหมดจริงด้วย --init-owner และรหัสผ่านอย่างน้อย 10 ตัวอักษร')
                c.execute('INSERT INTO Users(username,password_hash,role,name) VALUES(?,?,?,?)',
                          ('owner', password_hash('owner1234' if self.demo else owner_password), 'OWNER', 'เจ้าของร้าน (สาธิต)' if self.demo else 'เจ้าของร้าน'))
                if self.demo:
                    c.execute('INSERT INTO Users(username,password_hash,role,name) VALUES(?,?,?,?)', ('staff', password_hash('staff1234'), 'STAFF', 'พนักงาน (สาธิต)'))
                    for i, cap in enumerate([2,2,4,4,4,4,6,6], 1):
                        c.execute('INSERT INTO Tables(table_number,capacity) VALUES(?,?)', (f'T{i:02}',cap))
                    for name,cat,price in [('ข้าวกะเพราหมู','จานเดียว',65),('ข้าวผัดกุ้ง','จานเดียว',80),('ต้มยำกุ้ง','กับข้าว',150),('ไข่เจียว','กับข้าว',50),('ชาไทยเย็น','เครื่องดื่ม',40),('น้ำเปล่า','เครื่องดื่ม',15)]:
                        c.execute('INSERT INTO MenuItems(name,category,price,is_available) VALUES(?,?,?,1)',(name,cat,price*100))
                    for name,role,rate in [('นิด (สมมติ)','ครัว',450),('ต้น (สมมติ)','บริการ',400),('ฝน (สมมติ)','แคชเชียร์',400)]:
                        c.execute('INSERT INTO Staff(name,role,daily_rate) VALUES(?,?,?)',(name,role,rate*100))

    def _backfill_batches(self,c):
        # Recover each original submission from its transactional kitchen print job.
        for job in rows(c,"SELECT j.* FROM PrintJobs j WHERE j.kind='KITCHEN' ORDER BY j.job_id"):
            data=json.loads(job['payload'])
            order=c.execute('SELECT is_active FROM Orders WHERE order_id=?',(data['order_id'],)).fetchone()
            if not order or not order['is_active']:continue
            ids=[]
            for item in data['items']:
                candidates=rows(c,"SELECT i.order_item_id FROM OrderItems i WHERE i.order_id=? AND i.ordered_at=? AND i.name_snapshot=? AND i.quantity=? AND i.item_price=? AND i.note=? AND NOT EXISTS(SELECT 1 FROM OrderBatchItems bi WHERE bi.order_item_id=i.order_item_id) ORDER BY i.order_item_id",(data['order_id'],job['created_at'],item['name'],item['quantity'],item['price'],item['note']))
                match=next((i['order_item_id'] for i in candidates if i['order_item_id'] not in ids),None)
                if match:ids.append(match)
            if ids:self._create_batch(c,data['order_id'],ids,job['created_at'],job['job_id'],legacy=True)
        # Older imports without print jobs remain visible, marked for staff review.
        missing=rows(c,"SELECT i.* FROM OrderItems i JOIN Orders o USING(order_id) WHERE o.is_active=1 AND NOT EXISTS(SELECT 1 FROM OrderBatchItems bi WHERE bi.order_item_id=i.order_item_id) ORDER BY i.order_id,i.ordered_at,i.order_item_id")
        groups={}
        for i in missing:groups.setdefault((i['order_id'],i['ordered_at']),[]).append(i['order_item_id'])
        for (oid,stamp),ids in groups.items():self._create_batch(c,oid,ids,stamp,None,legacy=True)

    def _create_batch(self,c,order_id,item_ids,stamp,job_id,legacy=False):
        bid=c.execute('INSERT INTO OrderBatches(order_id,created_at,updated_at,kitchen_job_id,legacy) VALUES(?,?,?,?,?)',(order_id,stamp,stamp,job_id,int(legacy))).lastrowid
        c.executemany('INSERT INTO OrderBatchItems VALUES(?,?)',[(bid,i) for i in item_ids])
        c.execute("INSERT INTO OrderBatchEvents(batch_id,to_status,created_at) VALUES(?,'RECEIVED',?)",(bid,stamp))
        return bid

    def batches(self,c,order_id=None):
        if order_id is not None:
            batches=rows(c,'SELECT b.*,t.table_number,o.is_active FROM OrderBatches b JOIN Orders o USING(order_id) JOIN Tables t USING(table_id) WHERE b.order_id=? ORDER BY b.batch_id',(order_id,))
        else:
            batches=rows(c,"SELECT b.*,t.table_number,o.is_active FROM OrderBatches b JOIN Orders o USING(order_id) JOIN Tables t USING(table_id) WHERE o.is_active=1 OR b.status!='SERVED' OR substr(b.updated_at,1,10)=? ORDER BY b.batch_id",(self.today(),))
        ids={b['batch_id']:b for b in batches}
        for b in batches:b['items']=[]
        if ids:
            # Scope item reads in SQL, without SQLite's IN parameter limit.
            condition='b.order_id=?' if order_id is not None else "(o.is_active=1 OR b.status!='SERVED' OR substr(b.updated_at,1,10)=?)"
            arg=order_id if order_id is not None else self.today()
            for i in rows(c,'SELECT bi.batch_id,i.* FROM OrderBatchItems bi JOIN OrderItems i USING(order_item_id) JOIN OrderBatches b USING(batch_id) JOIN Orders o ON o.order_id=b.order_id WHERE '+condition+' ORDER BY i.order_item_id',(arg,)):
                if i['batch_id'] in ids:ids[i['batch_id']]['items'].append(i)
        return batches

    def user(self, token):
        c = self.connect()
        try:
            found = c.execute('SELECT u.user_id,u.username,u.role,u.name FROM Sessions s JOIN Users u USING(user_id) WHERE s.token=? AND s.expires_at>?', (token, self.stamp())).fetchone()
            return dict(found) if found else None
        finally:
            c.close()

    def auth(self, user, owner=False):
        require(user, 'กรุณาเข้าสู่ระบบ', 401)
        require(not owner or user['role']=='OWNER', 'รายการนี้สำหรับเจ้าของร้าน', 403)

    def open_day(self, c):
        require(not c.execute('SELECT 1 FROM DailySettlements WHERE settlement_date=?',(self.today(),)).fetchone(), 'วันนี้ปิดบัญชีแล้ว เปิดให้บริการอีกครั้งในวันถัดไป', 409)

    def slots(self, c, guests=1):
        cap = int(one(c,"SELECT value FROM Settings WHERE key='slot_capacity'")['value'])
        result = []
        for d in [self.now().date(), (self.now()+timedelta(days=1)).date()]:
            closed = c.execute('SELECT 1 FROM DailySettlements WHERE settlement_date=?',(d.isoformat(),)).fetchone()
            for hour in range(11,16):
                dt = datetime(d.year,d.month,d.day,hour,tzinfo=TZ)
                used = c.execute("SELECT COALESCE(SUM(guest_count),0) FROM Reservations WHERE reservation_datetime=? AND status IN ('CONFIRMED','CHECKED_IN')",(dt.isoformat(timespec='seconds'),)).fetchone()[0]
                reason = ('ร้านหยุดวันจันทร์' if not accepts_bookings_on(d) else
                          'ปิดบัญชีแล้ว' if closed else
                          'พ้นเวลาแล้ว' if dt <= self.now() else
                          'ที่นั่งไม่พอ' if cap-used < guests else '')
                result.append(dict(datetime=dt.isoformat(timespec='seconds'),remaining=cap-used,capacity=cap,available=not reason,reason=reason))
        return result

    def available_slots(self,guests=1):
        count=integer(guests)
        c=self.connect()
        try:return self.slots(c,count)
        finally:c.close()

    def audit(self, c, user, action, entity):
        c.execute('INSERT INTO AuditLog(actor,action,entity_id,created_at) VALUES(?,?,?,?)', (str(user['user_id']) if user else 'CUSTOMER',action,str(entity),self.stamp()))

    def print_job(self,c,kind,payload):
        return c.execute('INSERT INTO PrintJobs(kind,payload,created_at) VALUES(?,?,?)',(kind,json.dumps(payload,ensure_ascii=False),self.stamp())).lastrowid

    def assign_table(self,c,table_id,guests):
        t=one(c,'SELECT * FROM Tables WHERE table_id=?',(integer(table_id,1,100000),))
        require(Table.from_row(t).can_assign(guests),'โต๊ะไม่ว่างหรือจำนวนที่นั่งไม่เพียงพอ',409)
        c.execute("UPDATE Tables SET status='HELD' WHERE table_id=?",(t['table_id'],))
        return t

    def snapshot(self,user,date=None):
        self.auth(user)
        date=date or self.today()
        calendar_date(date)
        c=self.connect()
        try:
            c.execute('BEGIN')
            state=dict(tables=rows(c,'SELECT t.*,o.order_id,o.total_amount FROM Tables t LEFT JOIN Orders o ON o.table_id=t.table_id AND o.is_active=1 ORDER BY t.table_id'),
                queues=rows(c,'SELECT * FROM Queues WHERE service_date=? ORDER BY queue_number',(self.today(),)),
                reservations=rows(c,'SELECT * FROM Reservations WHERE substr(reservation_datetime,1,10)=? ORDER BY reservation_datetime,reservation_id',(date,)),
                menu=rows(c,"SELECT m.*,COALESCE(c.review_note,'') review_note,COALESCE(c.source_key,'') catalog_key FROM MenuItems m LEFT JOIN MenuCatalog c USING(menu_id) WHERE COALESCE(c.source_key,'') NOT LIKE 'legacy-demo:%' ORDER BY category,menu_id"),
                print_jobs=rows(c,'SELECT * FROM PrintJobs ORDER BY job_id DESC LIMIT 100'),
                kitchen_batches=self.batches(c),
                closed=bool(c.execute('SELECT 1 FROM DailySettlements WHERE settlement_date=?',(self.today(),)).fetchone()))
            if user['role']=='OWNER':
                state.update(staff=rows(c,'SELECT * FROM Staff ORDER BY staff_id'),
                    sales=self.sales(c,date),settlements=rows(c,'SELECT * FROM DailySettlements ORDER BY settlement_date DESC'),
                    wages=rows(c,'SELECT * FROM DailyWages ORDER BY wage_id DESC'),
                    audit=rows(c,'SELECT * FROM AuditLog ORDER BY audit_id DESC LIMIT 100'),
                    settings=dict(rows_as_pairs(c,'SELECT key,value FROM Settings')))
            return state
        finally:
            c.close()

    def sales(self,c,date):
        payments=rows(c,'SELECT p.*,t.table_number FROM Payments p JOIN Orders o USING(order_id) JOIN Tables t USING(table_id) WHERE substr(payment_time,1,10)=? ORDER BY payment_id DESC',(date,))
        return dict(total=sum(p['total_paid'] for p in payments),cash=sum(p['total_paid'] for p in payments if Payment.from_row(p).is_cash()),qr=sum(p['total_paid'] for p in payments if p['payment_method']=='MOCK_QR'),count=len(payments),payments=payments)

    def guest(self,token):
        c=self.connect()
        try:
            c.execute('BEGIN')
            o=one(c,'SELECT o.*,t.table_number FROM Orders o JOIN Tables t USING(table_id) WHERE session_token=? AND is_active=1',(token,), 'QR นี้หมดอายุหรือโต๊ะปิดแล้ว')
            return dict(batches=self.batches(c,o['order_id']),order={k:o[k] for k in ['order_id','table_number','total_amount']},menu=rows(c,"SELECT m.*,c.source_key catalog_key FROM MenuItems m LEFT JOIN MenuCatalog c USING(menu_id) WHERE m.is_available=1 AND COALESCE(c.review_note,'')='' AND COALESCE(c.source_key,'') NOT LIKE 'legacy-demo:%' ORDER BY category,menu_id"),items=rows(c,'SELECT * FROM OrderItems WHERE order_id=? ORDER BY order_item_id',(o['order_id'],)))
        finally:
            c.close()

    def bill(self,user,order_id):
        self.auth(user)
        c=self.connect()
        try:
            o=one(c,'SELECT o.*,t.table_number FROM Orders o JOIN Tables t USING(table_id) WHERE order_id=?',(integer(order_id,1,10000000),))
            return dict(order=o,items=rows(c,'SELECT * FROM OrderItems WHERE order_id=?',(o['order_id'],)),payment=rows(c,'SELECT * FROM Payments WHERE order_id=?',(o['order_id'],)))
        finally:c.close()

    def print_job_data(self,user,job_id):
        self.auth(user)
        c=self.connect()
        try:
            job=one(c,'SELECT * FROM PrintJobs WHERE job_id=?',(integer(job_id,1,10000000),))
            payload=json.loads(job['payload'])
            bill=self.bill(user,payload['order_id']) if job['kind']=='RECEIPT' else None
            return dict(job=job,payload=payload,bill=bill)
        finally:c.close()

    def report_data(self,user,date=None):
        self.auth(user,True)
        date=date or self.today()
        calendar_date(date)
        c=self.connect()
        try:
            c.execute('BEGIN')
            sales=self.sales(c,date)
            settlement=c.execute('SELECT * FROM DailySettlements WHERE settlement_date=?',(date,)).fetchone()
            wages=rows(c,'SELECT * FROM DailyWages WHERE settlement_id=?',(settlement['settlement_id'],)) if settlement else []
            return dict(date=date,sales=sales,settlement=dict(settlement) if settlement else None,wages=wages)
        finally:c.close()

    def mutate(self,action,b,user,key):
        require(isinstance(b,dict),'ข้อมูลต้องเป็น object')
        public={'reserve','cancel','lookup','place_order','login'}
        owners={'menu_save','settle','no_show','settings','table_save','staff_save','user_save'}
        if action not in public:self.auth(user,action in owners)
        require(isinstance(key,str) and 8<=len(key)<=100,'ต้องระบุรหัสคำขอสำหรับป้องกันการกดซ้ำ')
        scope=(str(user['user_id']) if user else 'PUBLIC')+':'+action
        if action=='place_order':scope+=':'+str(b.get('token',''))
        digest=hashlib.sha256(json.dumps(b,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.transaction() as c:
            prior=c.execute('SELECT * FROM Requests WHERE scope=? AND request_key=?',(scope,key)).fetchone()
            if prior:
                require(prior['body_hash']==digest,'รหัสคำขอซ้ำแต่ข้อมูลต่างกัน กรุณารีเฟรช',409)
                return json.loads(prior['response'])
            result=self._dispatch(c,action,b,user)
            if action!='login':
                c.execute('INSERT INTO Requests VALUES(?,?,?,?,?)',(key,scope,digest,json.dumps(result,ensure_ascii=False),self.stamp()))
            self.audit(c,user,action,result.get('id',''))
            return result

    def _dispatch(self,c,a,b,u):
        route=self._operation_routes.get(a)
        if route is None:raise Problem('ไม่พบคำสั่ง',404)
        group,method=route
        return getattr(self.operations[group],method)(c,b,u)
