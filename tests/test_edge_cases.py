"""Boundary, adversarial input, race and rollback tests against disposable SQLite DBs."""
import concurrent.futures,json,random,sqlite3,tempfile,unittest
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
from models.common import Problem,integer,money
from models.restaurant import Restaurant,TZ
from models.entities import DailySettlement

class EdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.time=datetime(2026,11,5,10,tzinfo=TZ)
        self.app=Restaurant(Path(self.tmp.name)/'edge.sqlite3',True,lambda:self.time);self.app.initialize()
        self.owner={'user_id':1,'role':'OWNER'};self.staff={'user_id':2,'role':'STAFF'};self.seq=0
    def tearDown(self):self.tmp.cleanup()
    def call(self,a,b=None,user='owner',key=None):
        self.seq+=1;return self.app.mutate(a,b or {},self.owner if user=='owner' else self.staff if user=='staff' else None,key or f'edge-key-{self.seq:08}')
    def rows(self,sql,args=()):
        c=self.app.connect()
        try:return [dict(r) for r in c.execute(sql,args)]
        finally:c.close()
    def reserve(self,**changes):
        b=dict(name='ทดสอบ',phone='0000000000',guests=2,slot='2026-11-05T11:00:00+07:00');b.update(changes);return self.call('reserve',b,None)
    def opened(self):return self.call('open_table',{'table_id':1},'staff')
    def item(self,**changes):
        x=dict(menu_id=1,quantity=1,expected_price=6500,note='');x.update(changes);return x
    def assert_clean(self):
        c=self.app.connect()
        try:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:c.close()
    def test_integer_adversarial_and_extreme_inputs_are_domain_errors(self):
        for value in [None,True,False,[],{},1.0,-1,0,21,'',' ','1.0','1e0','²','①','-1','9'*5000]:
            with self.subTest(value=str(value)[:35]),self.assertRaises(Problem):integer(value)
        for value,expected in [('0001',1),('20',20),(1,1),(20,20)]:self.assertEqual(integer(value),expected)
    def test_money_boundaries_and_exact_satang(self):
        for value in [None,True,False,[],{},'',-1,'-0.01','NaN','Infinity','-Infinity','0.001','10000000.01','1e999999']:
            with self.subTest(value=str(value)[:35]),self.assertRaises(Problem):money(value)
        for v,e in [('0',0),('0.01',1),('0.10',10),('10000000',1000000000),('1.2300',123)]:self.assertEqual(money(v),e)
        rng=random.Random(517)
        for _ in range(250):
            cents=rng.randrange(0,1000000001);self.assertEqual(money(Decimal(cents)/100),cents)
    def test_booking_name_phone_slot_and_party_matrix_has_no_partial_writes(self):
        cases=[('name',v) for v in ['', ' '*4, 'ก'*101,None,7,[],{}]]+[('phone',v) for v in ['', '1234567890','00000000','00000000000','๐๘๐๐๐๐๐๐๐๐',None,0,[]]]+[('guests',v) for v in [0,7,21,-1,True,None,1.5,'²',{}]]+[('slot',v) for v in [None,[],{},'','2026-11-04T11:00:00+07:00','2026-11-07T11:00:00+07:00','2026-11-05T11:30:00+07:00','2026-11-05T11:00:00Z']]
        for field,v in cases:
            with self.subTest(field=field,value=str(v)[:30]),self.assertRaises(Problem):self.reserve(**{field:v})
        self.assertFalse(self.rows('SELECT * FROM Reservations'));self.assertFalse(self.rows('SELECT * FROM Requests'));self.assert_clean()
    def test_booking_exact_start_and_day_rollover(self):
        self.time=self.time.replace(hour=10,minute=59,second=59);r=self.reserve(name='ก'*100,phone='000000000')
        self.time+=timedelta(seconds=1)
        with self.assertRaises(Problem):self.reserve()
        with self.assertRaises(Problem):self.call('cancel',{'code':r['code'],'phone':'000000000'},None)
        self.time=datetime(2026,11,5,23,59,59,tzinfo=TZ)
        self.reserve(slot='2026-11-06T11:00:00+07:00');self.time+=timedelta(seconds=1)
        self.reserve(slot='2026-11-07T11:00:00+07:00');self.assert_clean()
    def test_concurrent_same_request_reservation_is_exactly_once(self):
        body=dict(name='ทดสอบพร้อมกัน',phone='0000000000',guests=2,slot='2026-11-05T11:00:00+07:00')
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
            results=list(ex.map(lambda _:self.app.mutate('reserve',body,None,'one-booking-retry'),range(24)))
        self.assertEqual(len({r['id'] for r in results}),1);self.assertEqual(len(self.rows('SELECT * FROM Reservations')),1);self.assert_clean()
    def test_concurrent_table_open_and_queue_allocation_have_single_winner(self):
        def attempt(i):
            try:return self.app.mutate('open_table',{'table_id':1},self.staff,f'open-race-{i:03}')
            except Problem as e:self.assertEqual(e.status,409);return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(attempt,range(16)))
        self.assertEqual(sum(x is not None for x in results),1);self.assertEqual(len(self.rows('SELECT * FROM Orders')),1)
        q1=self.call('queue_create',{'guests':2},'staff');q2=self.call('queue_create',{'guests':2},'staff')
        for q in (q1,q2):self.call('queue_call',{'id':q['id']},'staff')
        def seat(q):
            try:return self.app.mutate('queue_seat',{'id':q['id'],'table_id':2},self.staff,f"seat-race-{q['id']}")
            except Problem as e:self.assertEqual(e.status,409);return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(seat,[q1,q2]))
        self.assertEqual(sum(x is not None for x in results),1);self.assertEqual(len(self.rows("SELECT * FROM Queues WHERE status='SEATED'")),1);self.assert_clean()
    def test_concurrent_order_and_cash_payment_remain_balanced(self):
        o=self.opened();self.call('place_order',{'token':o['token'],'items':[self.item()]},None)
        def submit():
            try:return self.app.mutate('place_order',{'token':o['token'],'items':[self.item()]},None,'racing-order-key')
            except Problem as e:self.assertEqual(e.status,404);return None
        def pay():
            try:return self.app.mutate('pay',dict(id=o['id'],method='CASH',received='65',expected_total=6500),self.staff,'racing-pay-key')
            except Problem as e:self.assertEqual(e.status,409);return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:out=[f.result() for f in [ex.submit(submit),ex.submit(pay)]]
        order=self.rows('SELECT * FROM Orders')[0];items=self.rows('SELECT * FROM OrderItems');payments=self.rows('SELECT * FROM Payments')
        self.assertEqual(order['total_amount'],sum(i['quantity']*i['item_price'] for i in items))
        if payments:self.assertEqual(payments[0]['total_paid'],order['total_amount']);self.assertEqual(order['is_active'],0)
        else:self.assertEqual(order['is_active'],1);self.assertIsNotNone(out[0])
        self.assert_clean()
    def test_invalid_cart_matrix_rolls_back_all_related_tables(self):
        o=self.opened();bad=[self.item(quantity=v) for v in [0,100,-1,True,None,1.2,'²',{}]]+[self.item(note=v) for v in ['ก'*256,None,7,{}]]+[self.item(menu_id=999999),self.item(expected_price=1),None,[]]
        for item in bad:
            with self.subTest(item=str(item)[:60]),self.assertRaises(Problem):self.call('place_order',{'token':o['token'],'items':[self.item(),item]},None)
        for table in ['OrderItems','OrderBatches','OrderBatchItems','OrderBatchEvents']:self.assertFalse(self.rows('SELECT * FROM '+table))
        self.assertEqual(len(self.rows('SELECT * FROM PrintJobs')),1);self.assertEqual(self.rows('SELECT total_amount FROM Orders')[0]['total_amount'],0)
        self.call('place_order',{'token':o['token'],'items':[self.item(quantity=99,note='ก'*255)]},None);self.assert_clean()
    def test_cart_size_limits_and_duplicate_lines_have_correct_totals(self):
        o=self.opened()
        for cart in [[],None,{},[self.item()]*51]:
            with self.subTest(size=str(type(cart))),self.assertRaises(Problem):self.call('place_order',{'token':o['token'],'items':cart},None)
        self.call('place_order',{'token':o['token'],'items':[self.item()]*50},None)
        self.assertEqual(self.rows('SELECT total_amount FROM Orders')[0]['total_amount'],325000);self.assertEqual(len(self.rows('SELECT * FROM OrderBatchItems')),50);self.assert_clean()
    def test_sql_injection_strings_remain_data_and_foreign_keys_enforced(self):
        name="Robert'); DROP TABLE Reservations;--";r=self.reserve(name=name)
        self.assertEqual(self.rows('SELECT customer_name FROM Reservations')[0]['customer_name'],name)
        with self.assertRaises(Problem):self.call('lookup',{'code':"' OR 1=1 --",'phone':'0000000000'},None)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.transaction() as c:c.execute('UPDATE Reservations SET table_id=99999 WHERE reservation_id=?',(r['id'],))
        self.assert_clean()
    def test_expired_token_at_exact_twelve_hours(self):
        result=self.call('login',{'username':'staff','password':'staff1234'},None);self.time+=timedelta(hours=12,seconds=-1)
        self.assertIsNotNone(self.app.user(result['token']));self.time+=timedelta(seconds=1);self.assertIsNone(self.app.user(result['token']))
    def test_every_write_route_enforces_anonymous_and_staff_permissions(self):
        public={'reserve','cancel','lookup','place_order','login'};owner_only={'menu_save','settle','no_show','settings','table_save','staff_save','user_save'}
        for action in self.app._operation_routes:
            if action not in public:
                with self.subTest(action=action,role='anonymous'),self.assertRaises(Problem) as e:self.call(action,{},None)
                self.assertEqual(e.exception.status,401)
            if action in owner_only:
                with self.subTest(action=action,role='staff'),self.assertRaises(Problem) as e:self.call(action,{},'staff')
                self.assertEqual(e.exception.status,403)
    def test_allocation_properties_over_random_money_values(self):
        rng=random.Random(957)
        for _ in range(500):
            sales,material,labor,prior=[rng.randrange(0,10000000) for _ in range(4)]
            x=DailySettlement.compute(sales,material,labor,prior)
            self.assertEqual(x.net,sales-material-labor);self.assertEqual(x.distributable,max(0,x.net-prior));self.assertEqual(x.next_loss,max(0,prior-x.net))
            self.assertEqual(sum(x.shares),x.distributable);self.assertLessEqual(max(x.shares)-min(x.shares),1)
    def test_report_dates_must_be_real_calendar_dates(self):
        for value in ['2026-02-30','2026-13-01','0000-01-01','abc','2026-1-1']:
            for method in [self.app.snapshot,self.app.report_data]:
                with self.subTest(value=value,method=method.__name__),self.assertRaises(Problem):method(self.owner,value)

    def test_same_order_retry_race_has_one_batch_and_one_line(self):
        o=self.opened();body={'token':o['token'],'items':[self.item()]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:out=list(ex.map(lambda _:self.app.mutate('place_order',body,None,'one-order-retry'),range(24)))
        self.assertEqual(len({x['batch_id'] for x in out}),1)
        for table in ['OrderItems','OrderBatches','OrderBatchItems']:self.assertEqual(len(self.rows('SELECT * FROM '+table)),1)
        self.assert_clean()
    def test_parallel_walkin_numbers_are_unique_and_contiguous(self):
        def create(n):return self.app.mutate('queue_create',{'guests':2},self.staff,f'walkin-race-{n:03}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:out=list(ex.map(create,range(24)))
        self.assertEqual(len({x['id'] for x in out}),24);self.assertEqual([r['queue_number'] for r in self.rows('SELECT queue_number FROM Queues ORDER BY queue_number')],list(range(1,25)));self.assert_clean()
    def test_failed_idempotent_request_can_retry_after_correcting_price(self):
        o=self.opened();body={'token':o['token'],'items':[self.item(expected_price=1)]}
        with self.assertRaises(Problem):self.call('place_order',body,None,'retry-after-failure')
        self.assertFalse(self.rows("SELECT * FROM Requests WHERE request_key='retry-after-failure'"))
        body['items'][0]['expected_price']=6500
        first=self.call('place_order',body,None,'retry-after-failure');second=self.call('place_order',body,None,'retry-after-failure')
        self.assertEqual(first,second);self.assertEqual(len(self.rows('SELECT * FROM OrderItems')),1);self.assert_clean()
    def test_one_satang_cash_payment_change_and_settlement_remainder(self):
        self.call('menu_save',dict(id=1,name='ทดสอบสตางค์',category='ทดสอบ',price='0.01',available=True))
        o=self.opened();self.call('place_order',{'token':o['token'],'items':[self.item(expected_price=1,quantity=5)]},None)
        self.assertEqual(self.call('pay',dict(id=o['id'],method='CASH',received='0.06',expected_total=5),'staff')['change'],1)
        x=self.call('settle',dict(material='0',actual_cash='0.05',staff_ids=[]));self.assertEqual(x['shares'],[2,1,1,1]);self.assert_clean()
    def test_inactive_staff_and_duplicate_canonical_staff_ids_roll_back_settlement(self):
        self.call('staff_save',dict(id=1,name='ทดสอบ',role='บริการ',rate='400',active=False))
        with self.assertRaises(Problem):self.call('settle',dict(material='0',actual_cash='0',staff_ids=[1]))
        with self.assertRaises(sqlite3.IntegrityError):self.call('settle',dict(material='0',actual_cash='0',staff_ids=[2,'02']))
        self.assertFalse(self.rows('SELECT * FROM DailySettlements'));self.assertFalse(self.rows('SELECT * FROM DailyWages'));self.assert_clean()
    def test_held_or_occupied_tables_cannot_be_renamed_or_shrunk(self):
        r=self.reserve();self.call('checkin',dict(id=r['id'],table_id=1),'staff')
        for status in ('HELD','OCCUPIED'):
            with self.subTest(status=status),self.assertRaises(Problem):self.call('table_save',dict(id=1,number='T-NEW',capacity=1))
            if status=='HELD':self.opened()
        self.assertEqual(self.rows('SELECT table_number,capacity FROM Tables WHERE table_id=1')[0],dict(table_number='T01',capacity=2));self.assert_clean()
    def test_random_complete_orders_reconcile_to_cash_qr_and_final_allocation(self):
        rng=random.Random(2005);expected=0;cash=0;qr=0
        for n in range(24):
            o=self.opened();total=0
            for _ in range(rng.randrange(1,4)):
                qty=rng.randrange(1,6);total+=qty*6500
                self.call('place_order',dict(token=o['token'],items=[self.item(quantity=qty)]),None)
            method='CASH' if n%2 else 'MOCK_QR';args=dict(id=o['id'],method=method,expected_total=total)
            if method=='CASH':args['received']=str(Decimal(total)/100+10);cash+=total
            else:args['confirmed']=True;qr+=total
            self.call('pay',args,'staff');expected+=total
        sales=self.app.snapshot(self.owner)['sales'];self.assertEqual((sales['total'],sales['cash'],sales['qr'],sales['count']),(expected,cash,qr,24))
        settled=self.call('settle',dict(material='123.45',actual_cash=str(Decimal(cash)/100),staff_ids=[1,2,3]))
        row=self.rows('SELECT * FROM DailySettlements')[0];self.assertEqual(row['net_profit_loss'],expected-12345-125000)
        self.assertEqual(sum(settled['shares']),max(0,row['net_profit_loss']));self.assertEqual(len(self.rows('SELECT * FROM Payments WHERE settlement_id IS NOT NULL')),24);self.assert_clean()
