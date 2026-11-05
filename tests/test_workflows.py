import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from service import Restaurant, Problem, TZ, money
import qr


class Workflows(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.time=datetime(2026,10,27,10,0,tzinfo=TZ)
        self.app=Restaurant(Path(self.tmp.name)/'test.sqlite3',True,lambda:self.time)
        self.app.initialize()
        self.owner={'user_id':1,'role':'OWNER','name':'owner'}
        self.staff={'user_id':2,'role':'STAFF','name':'staff'}
        self.seq=0

    def tearDown(self):self.tmp.cleanup()

    def call(self,a,b=None,u='owner',key=None):
        self.seq+=1
        return self.app.mutate(a,b or {},self.owner if u=='owner' else self.staff if u=='staff' else None,key or f'test-key-{self.seq:05}')

    def sql(self,sql,args=()):
        c=self.app.connect()
        try:return [dict(r) for r in c.execute(sql,args)]
        finally:c.close()

    def reserve(self,slot='2026-10-27T11:00:00+07:00',guests=2,**kwargs):
        return self.call('reserve',dict(name='ลูกค้าสมมติ',phone='0800000000',guests=guests,slot=slot),None,**kwargs)

    def opened(self,table=1):return self.call('open_table',{'table_id':table},'staff')

    def order(self,o,qty=1,key=None):
        return self.call('place_order',{'token':o['token'],'items':[{'menu_id':1,'quantity':qty,'expected_price':6500,'note':'เผ็ดน้อย'}]},None,key)

    def payment(self,o,**kw):return self.call('pay',dict(id=o['id'],method='CASH',received='100.00',expected_total=6500,**kw),'staff')

    def test_res01_02_reserve_and_empty_alternative_slots(self):
        c=self.app.connect()
        try:self.assertEqual(len(self.app.slots(c)),10)
        finally:c.close()
        for _ in range(5):self.reserve(guests=4)
        with self.assertRaises(Problem) as caught:self.reserve()
        self.assertEqual(caught.exception.status,409)
        self.assertTrue(any(s['datetime']=='2026-10-27T12:00:00+07:00' for s in caught.exception.details['alternatives']))
        self.assertEqual(self.sql('SELECT COUNT(*) n FROM Reservations')[0]['n'],5)

    def test_res01_validation_past_future_phone_capacity(self):
        for data in [dict(name='',phone='0800000000',guests=2,slot=''),dict(name='x',phone='abc',guests=2,slot=''),dict(name='x',phone='0800000000',guests=0,slot='')]:
            with self.assertRaises(Problem):self.call('reserve',data,None)
        with self.assertRaises(Problem):self.reserve('2026-10-26T11:00:00+07:00')
        with self.assertRaises(Problem):self.reserve('2026-10-29T11:00:00+07:00')
        with self.assertRaises(Problem):self.reserve(guests=7)
        self.assertFalse(self.sql('SELECT * FROM Reservations'))

    def test_restaurant_closed_monday_is_not_an_alternative_slot(self):
        self.time=datetime(2026,11,1,10,0,tzinfo=TZ)  # Sunday: tomorrow is Monday.
        c=self.app.connect()
        try:slots=self.app.slots(c)
        finally:c.close()
        monday=[s for s in slots if s['datetime'].startswith('2026-11-02')]
        self.assertEqual(len(monday),5)
        self.assertTrue(all(not s['available'] and s['reason']=='ร้านหยุดวันจันทร์' for s in monday))
        with self.assertRaises(Problem) as error:self.reserve('2026-11-02T11:00:00+07:00')
        self.assertTrue(all(not s['datetime'].startswith('2026-11-02') for s in error.exception.details['alternatives']))

    def test_monday_still_allows_booking_for_tuesday(self):
        self.time=datetime(2026,11,2,10,0,tzinfo=TZ)
        with self.assertRaises(Problem):self.reserve('2026-11-02T11:00:00+07:00')
        self.reserve('2026-11-03T11:00:00+07:00')
        self.assertEqual(len(self.sql('SELECT * FROM Reservations')),1)

    def test_res08_lookup_cancel_and_release_quota(self):
        r=self.reserve()
        data={'code':r['code'],'phone':'0800000000'}
        found=self.call('lookup',data,None)['reservation'];self.assertEqual(found['status'],'CONFIRMED')
        with self.assertRaises(Problem):self.call('cancel',dict(code=r['code'],phone='0811111111'),None)
        self.call('cancel',data,None)
        with self.assertRaises(Problem):self.call('cancel',data,None)
        self.assertEqual(self.sql('SELECT status FROM Reservations')[0]['status'],'CANCELLED')
        c=self.app.connect()
        try:self.assertEqual(self.app.slots(c)[0]['remaining'],20)
        finally:c.close()

    def test_res08_cancel_after_time_blocked(self):
        r=self.reserve();self.time=self.time.replace(hour=11,minute=1)
        with self.assertRaises(Problem):self.call('cancel',{'code':r['code'],'phone':'0800000000'},None)

    def test_res05_06_checkin_hold_prevents_duplicate_allocation(self):
        r=self.reserve();r2=self.reserve()
        self.call('checkin',{'id':r['id'],'table_id':1},'staff')
        self.assertEqual(self.app.snapshot(self.owner)['reservations'][0]['status'],'CHECKED_IN')
        self.assertEqual(self.sql('SELECT status FROM Tables WHERE table_id=1')[0]['status'],'HELD')
        with self.assertRaises(Problem):self.call('checkin',{'id':r2['id'],'table_id':1},'staff')
        self.assertEqual(self.sql('SELECT status FROM Reservations WHERE reservation_id=?',(r2['id'],))[0]['status'],'CONFIRMED')
        self.opened()
        with self.assertRaises(Problem):self.call('no_show',{'id':r['id']})
        c=self.app.connect()
        try:self.assertEqual(self.app.slots(c)[0]['remaining'],16)
        finally:c.close()

    def test_res05_wrong_day_and_small_table(self):
        r=self.reserve('2026-10-28T11:00:00+07:00')
        with self.assertRaises(Problem):self.call('checkin',{'id':r['id'],'table_id':1})
        r=self.reserve(guests=4)
        with self.assertRaises(Problem):self.call('checkin',{'id':r['id'],'table_id':1})

    def test_res07_owner_confirmed_after_grace_and_audit(self):
        r=self.reserve()
        self.time=self.time.replace(hour=11,minute=15)
        with self.assertRaises(Problem):self.call('no_show',{'id':r['id']})
        self.time+=timedelta(seconds=1)
        with self.assertRaises(Problem):self.call('no_show',{'id':r['id']},'staff')
        self.call('no_show',{'id':r['id']})
        self.assertEqual(self.sql('SELECT status FROM Reservations')[0]['status'],'NO_SHOW')
        self.assertTrue(self.sql("SELECT * FROM AuditLog WHERE action='no_show'"))

    def test_res03_04_queue_fifo_calls_skip_and_assignment(self):
        q1=self.call('queue_create',{'name':'หนึ่ง','guests':2},'staff');q2=self.call('queue_create',{'name':'สอง','guests':4},'staff')
        with self.assertRaises(Problem):self.call('queue_call',{'id':q2['id']},'staff')
        with self.assertRaises(Problem):self.call('queue_skip',{'id':q1['id']},'staff')
        for _ in range(3):self.call('queue_call',{'id':q1['id']},'staff')
        with self.assertRaises(Problem):self.call('queue_call',{'id':q1['id']},'staff')
        self.call('queue_skip',{'id':q1['id']},'staff')
        self.call('queue_call',{'id':q2['id']},'staff')
        with self.assertRaises(Problem):self.call('queue_seat',{'id':q2['id'],'table_id':1},'staff')
        self.call('queue_seat',{'id':q2['id'],'table_id':3},'staff')
        self.assertEqual([q['status'] for q in self.sql('SELECT * FROM Queues ORDER BY queue_id')],['SKIPPED','SEATED'])
        self.assertEqual(self.sql('SELECT status FROM Tables WHERE table_id=3')[0]['status'],'HELD')
        self.assertEqual(len(self.sql("SELECT * FROM PrintJobs WHERE kind='QUEUE'")),2)

    def test_queue_cancel_and_print_failure_retains_history(self):
        q=self.call('queue_create',{'guests':2},'staff')
        self.call('print_status',{'id':q['job_id'],'status':'FAILED'},'staff')
        self.call('print_status',{'id':q['job_id'],'status':'PRINTED'},'staff')
        self.assertEqual(self.sql('SELECT attempts FROM PrintJobs')[0]['attempts'],2)
        self.call('queue_cancel',{'id':q['id']},'staff')
        self.assertEqual(len(self.sql('SELECT * FROM Queues')),1)

    def test_ord01_02_pay01_cash_lifecycle_and_persistence(self):
        o=self.opened()
        with self.assertRaises(Problem):self.opened()
        self.assertEqual(self.app.guest(o['token'])['order']['table_number'],'T01')
        self.order(o);self.order(o)
        p=self.call('pay',{'id':o['id'],'method':'CASH','received':'200','expected_total':13000},'staff')
        self.assertEqual(p['change'],7000)
        self.assertEqual(self.sql('SELECT status FROM Tables WHERE table_id=1')[0]['status'],'AVAILABLE')
        with self.assertRaises(Problem):self.app.guest(o['token'])
        with self.assertRaises(Problem):self.order(o)
        with self.assertRaises(Problem):self.payment(o)
        second=Restaurant(self.app.path,True,lambda:self.time)
        self.assertEqual(second.snapshot(self.owner)['sales']['total'],13000)
        self.assertNotEqual(self.opened()['token'],o['token'])

    def test_ord02_unavailable_price_change_and_atomic_cart(self):
        o=self.opened()
        self.call('menu_save',{'id':2,'name':'ข้าวผัดกุ้ง','category':'จานเดียว','price':'80','available':False})
        with self.assertRaises(Problem):self.call('place_order',{'token':o['token'],'items':[{'menu_id':1,'quantity':1,'expected_price':6500},{'menu_id':2,'quantity':1,'expected_price':8000}]},None)
        self.assertFalse(self.sql('SELECT * FROM OrderItems'))
        self.call('menu_save',{'id':1,'name':'ชื่อใหม่','category':'จานเดียว','price':'70','available':True})
        with self.assertRaises(Problem):self.order(o)
        self.assertFalse(self.sql('SELECT * FROM OrderItems'))

    def test_ord03_snapshot_preserves_old_names_and_prices(self):
        o=self.opened();self.order(o)
        self.call('menu_save',{'id':1,'name':'ใหม่','category':'จานเดียว','price':'99','available':True})
        i=self.app.bill(self.staff,o['id'])['items'][0]
        self.assertEqual(i['name_snapshot'],'ข้าวกะเพราหมู');self.assertEqual(i['item_price'],6500)
        with self.assertRaises(Problem):self.call('menu_save',{'name':'','category':'a','price':'-1','available':True})

    def test_pay01_mock_qr_requires_staff_confirmation(self):
        o=self.opened();self.order(o)
        data={'id':o['id'],'method':'MOCK_QR','expected_total':6500}
        with self.assertRaises(Problem):self.call('pay',data,'staff')
        self.call('pay',dict(data,confirmed=True),'staff')
        p=self.sql('SELECT * FROM Payments')[0];self.assertEqual(p['payment_method'],'MOCK_QR');self.assertEqual(p['change_amount'],0)

    def test_pay01_insufficient_cash_stale_total_empty_bill(self):
        o=self.opened()
        with self.assertRaises(Problem):self.payment(o)
        self.order(o)
        for data in [dict(id=o['id'],method='CASH',received='10',expected_total=6500),dict(id=o['id'],method='CASH',received='100',expected_total=6400)]:
            with self.assertRaises(Problem):self.call('pay',data,'staff')
        self.assertFalse(self.sql('SELECT * FROM Payments'))
        self.assertEqual(self.sql('SELECT is_active FROM Orders')[0]['is_active'],1)

    def test_empty_session_can_close_without_fabricated_payment(self):
        o=self.opened();self.call('close_empty',{'id':o['id']},'staff')
        self.assertFalse(self.sql('SELECT * FROM Payments'))
        self.assertEqual(self.sql('SELECT status FROM Tables WHERE table_id=1')[0]['status'],'AVAILABLE')

    def test_zero_price_items_can_close_without_a_payment(self):
        self.call('menu_save',{'id':1,'name':'ของแถมสาธิต','category':'จานเดียว','price':'0','available':True})
        o=self.opened()
        self.call('place_order',{'token':o['token'],'items':[{'menu_id':1,'quantity':1,'expected_price':0}]},None)
        self.call('close_empty',{'id':o['id']},'staff')
        self.assertEqual(len(self.sql('SELECT * FROM OrderItems')),1)
        self.assertFalse(self.sql('SELECT * FROM Payments'))

    def test_pay02_dashboard_counts_net_not_cash_tendered(self):
        o=self.opened();self.order(o);self.payment(o)
        s=self.app.snapshot(self.owner)['sales']
        self.assertEqual((s['total'],s['cash'],s['qr'],s['count']),(6500,6500,0,1))
        self.assertNotIn('sales',self.app.snapshot(self.staff))

    def test_acc01_02_settlement_wages_loss_carry_and_four_shares(self):
        o=self.opened();self.order(o);self.payment(o)
        self.call('settle',{'material':'10','actual_cash':'65','staff_ids':[1]})
        first=self.sql('SELECT * FROM DailySettlements')[0]
        self.assertEqual((first['net_profit_loss'],first['accumulated_loss'],first['distributable_profit']),(-39500,39500,0))
        self.assertEqual(len(self.sql('SELECT * FROM DailyWages')),1)
        self.assertEqual(self.sql('SELECT settlement_id FROM Payments')[0]['settlement_id'],first['settlement_id'])
        self.time+=timedelta(days=1)
        o=self.opened();self.order(o,10)
        self.call('pay',{'id':o['id'],'method':'CASH','received':'650','expected_total':65000},'staff')
        self.call('settle',{'material':'0.01','actual_cash':'650','staff_ids':[]})
        s=self.app.snapshot(self.owner)['settlements'][0]
        self.assertEqual(s['previous_loss'],39500);self.assertEqual(s['distributable_profit'],25499)
        self.assertEqual(json.loads(s['partner_shares']),[6375,6375,6375,6374])
        self.assertEqual(sum(json.loads(s['partner_shares'])),s['distributable_profit'])

    def test_acc01_blocks_pending_duplicate_and_after_closure(self):
        o=self.opened()
        data={'material':'0','actual_cash':'0','staff_ids':[]}
        with self.assertRaises(Problem):self.call('settle',data)
        self.call('close_empty',{'id':o['id']},'staff')
        self.call('settle',data)
        for a,b in [('settle',data),('open_table',{'table_id':1}),('queue_create',{'guests':2})]:
            with self.assertRaises(Problem):self.call(a,b)
        self.reserve('2026-10-28T11:00:00+07:00')

    def test_acc01_cash_discrepancy_requires_reason_and_no_duplicate_staff(self):
        with self.assertRaises(Problem):self.call('settle',{'material':'0','actual_cash':'5','staff_ids':[]})
        with self.assertRaises(Problem):self.call('settle',{'material':'0','actual_cash':'0','staff_ids':[1,1]})
        self.call('settle',{'material':'0','actual_cash':'5','staff_ids':[],'difference_note':'นับพบเกินในการสาธิต'})
        self.assertEqual(self.sql('SELECT cash_difference FROM DailySettlements')[0]['cash_difference'],500)

    def test_acc01_pending_queue_reservation_block_closing(self):
        r=self.reserve();q=self.call('queue_create',{'guests':2})
        data={'material':'0','actual_cash':'0','staff_ids':[]}
        with self.assertRaises(Problem):self.call('settle',data)
        self.call('queue_cancel',{'id':q['id']})
        with self.assertRaises(Problem):self.call('settle',data)
        self.call('cancel',{'code':r['code'],'phone':'0800000000'},None)
        self.call('settle',data)

    def test_idempotency_reserve_order_payment_settle(self):
        r1=self.reserve(key='same-reserve');r2=self.reserve(key='same-reserve');self.assertEqual(r1,r2)
        self.call('cancel',{'code':r1['code'],'phone':'0800000000'},None)
        o=self.opened();self.order(o,key='same-order');self.order(o,key='same-order')
        data={'id':o['id'],'method':'CASH','received':'100','expected_total':6500}
        self.call('pay',data,'staff','same-payment');self.call('pay',data,'staff','same-payment')
        data={'material':'0','actual_cash':'65','staff_ids':[]}
        self.call('settle',data,key='same-closing');self.call('settle',data,key='same-closing')
        for table in ['OrderItems','Payments','DailySettlements']:
            self.assertEqual(self.sql(f'SELECT COUNT(*) n FROM {table}')[0]['n'],1)
        with self.assertRaises(Problem):self.reserve(guests=3,key='same-reserve')

    def test_concurrent_quota_does_not_oversell(self):
        def work(i):
            try:return self.app.mutate('reserve',dict(name='test',phone='0800000000',guests=4,slot='2026-10-27T11:00:00+07:00'),None,f'parallel-{i}')
            except Problem:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(work,range(10)))
        self.assertEqual(sum(r is not None for r in results),5)
        self.assertEqual(self.sql('SELECT SUM(guest_count) n FROM Reservations')[0]['n'],20)

    def test_concurrent_pay_only_once(self):
        o=self.opened();self.order(o)
        def work(i):
            try:return self.app.mutate('pay',dict(id=o['id'],method='CASH',received='100',expected_total=6500),self.staff,f'parallel-pay-{i}')
            except Problem:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(work,range(4)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(len(self.sql('SELECT * FROM Payments')),1)

    def test_rollback_payment_on_print_outbox_failure(self):
        o=self.opened();self.order(o)
        with patch.object(self.app,'print_job',side_effect=sqlite3.OperationalError('injected disk error')):
            with self.assertRaises(sqlite3.OperationalError):self.payment(o)
        self.assertFalse(self.sql('SELECT * FROM Payments'))
        self.assertEqual(self.sql('SELECT is_active FROM Orders')[0]['is_active'],1)
        self.assertEqual(self.sql('SELECT status FROM Tables WHERE table_id=1')[0]['status'],'OCCUPIED')

    def test_rollback_settlement_when_wage_insert_fails(self):
        with self.app.transaction() as c:c.execute("CREATE TRIGGER test_fail BEFORE INSERT ON DailyWages BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.call('settle',{'material':'0','actual_cash':'0','staff_ids':[1]})
        self.assertFalse(self.sql('SELECT * FROM DailySettlements'))

    def test_database_immutability_foreign_keys_and_unique_session(self):
        o=self.opened();self.order(o);self.payment(o);self.call('settle',{'material':'0','actual_cash':'65','staff_ids':[]})
        for sql in ['UPDATE Payments SET total_paid=1','DELETE FROM Payments','UPDATE DailySettlements SET total_sales=1','DELETE FROM DailySettlements']:
            with self.assertRaises(sqlite3.IntegrityError):
                with self.app.transaction() as c:c.execute(sql)
        self.assertFalse(self.sql('PRAGMA foreign_key_check'))
        self.assertEqual(self.sql('PRAGMA integrity_check')[0]['integrity_check'],'ok')

    def test_auth_roles_sessions_logout(self):
        for a,b in [('menu_save',{}),('settle',{}),('no_show',{}),('settings',{}),('user_save',{})]:
            with self.assertRaises(Problem) as e:self.call(a,b,'staff')
            self.assertEqual(e.exception.status,403)
        with self.assertRaises(Problem):self.call('open_table',{'table_id':1},None)
        with self.assertRaises(Problem):self.call('login',{'username':'owner','password':'wrong'},None)
        r=self.call('login',{'username':'owner','password':'owner1234'},None)
        self.assertEqual(self.app.user(r['token'])['role'],'OWNER')
        self.call('logout',{},'owner');self.assertIsNone(self.app.user(r['token']))

    def test_live_database_has_no_demo_data_and_rejects_mode_mix(self):
        path=Path(self.tmp.name)/'live.sqlite3';live=Restaurant(path,False,lambda:self.time);live.initialize('strong-test-password')
        c=live.connect()
        try:
            for table in ['Tables','MenuItems','Staff','Reservations','Payments']:self.assertEqual(c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
        finally:c.close()
        with self.assertRaises(Problem):Restaurant(path,True).initialize()

    def test_admin_setup_and_money_input(self):
        self.call('table_save',{'number':'A9','capacity':8});self.call('staff_save',{'name':'new','role':'ครัว','rate':'450.50','active':True})
        self.call('settings',{'capacity':30})
        self.assertEqual(money('0.01'),1)
        for x in ['NaN','Infinity','1.001','-1','10000001',None]:
            with self.assertRaises(Problem):money(x)
        self.assertEqual(self.app.snapshot(self.owner)['settings']['slot_capacity'],'30')

    def test_new_staff_account_and_session_expiry(self):
        self.call('user_save',{'username':'new_staff','password':'new-test-password','name':'พนักงานใหม่สมมติ','role':'STAFF'})
        r=self.call('login',{'username':'new_staff','password':'new-test-password'},None)
        user=self.app.user(r['token']);self.assertEqual(user['role'],'STAFF')
        with self.assertRaises(Problem):self.app.mutate('settings',{'capacity':100},user,'new-staff-test')
        self.time+=timedelta(hours=13);self.assertIsNone(self.app.user(r['token']))

    def test_historical_wages_survive_staff_rate_and_name_change(self):
        self.call('settle',{'material':'0','actual_cash':'0','staff_ids':[1]})
        self.call('staff_save',{'id':1,'name':'ชื่อใหม่','role':'ครัว','rate':'999','active':False})
        wage=self.sql('SELECT * FROM DailyWages')[0]
        self.assertEqual((wage['name_snapshot'],wage['wage_amount']),('นิด (สมมติ)',45000))

    def test_qr_matrix_structure_limit_and_determinism(self):
        m=qr.matrix('http://127.0.0.1:8000/order/abcdefghijklmnopqrstuvwxyz123456')
        self.assertEqual(len(m),37);self.assertTrue(all(v in (0,1) for row in m for v in row))
        self.assertEqual(m,qr.matrix('http://127.0.0.1:8000/order/abcdefghijklmnopqrstuvwxyz123456'))
        self.assertIn('<svg',qr.svg('test'))
        with self.assertRaises(ValueError):qr.matrix('a'*107)


if __name__=='__main__':unittest.main(verbosity=2)
