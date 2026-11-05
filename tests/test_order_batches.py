import concurrent.futures
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from service import Restaurant, Problem, TZ


class OrderBatches(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.time=datetime(2026,10,27,11,tzinfo=TZ)
        self.app=Restaurant(Path(self.tmp.name)/'batches.sqlite3',True,lambda:self.time)
        self.app.initialize()
        self.staff={'user_id':2,'role':'STAFF'}
        self.owner={'user_id':1,'role':'OWNER'}
        self.seq=0
        self.table=self.call('open_table',{'table_id':1})

    def tearDown(self):self.tmp.cleanup()

    def call(self,action,body,user='staff',key=None):
        self.seq+=1
        return self.app.mutate(action,body,self.staff if user=='staff' else self.owner if user=='owner' else None,key or f'batch-test-{self.seq:04}')

    def order(self,token=None,key=None):
        return self.call('place_order',{'token':token or self.table['token'],'items':[{'menu_id':1,'quantity':2,'expected_price':6500,'note':'เผ็ดน้อย'},{'menu_id':6,'quantity':1,'expected_price':1500,'note':''}]},None,key)

    def status(self,bid,status,expected,key=None):
        return self.call('batch_status',dict(id=bid,status=status,expected_status=expected),key=key)

    def test_submissions_same_second_are_distinct_and_retries_do_not_duplicate(self):
        a=self.order(key='order-repeat-001');repeat=self.order(key='order-repeat-001');b=self.order()
        self.assertEqual(a,repeat);self.assertNotEqual(a['batch_id'],b['batch_id'])
        g=self.app.guest(self.table['token'])
        self.assertEqual(len(g['batches']),2)
        self.assertEqual([len(b['items']) for b in g['batches']],[2,2])
        self.assertEqual(g['order']['total_amount'],29000)
        self.status(a['batch_id'],'PREPARING','RECEIVED')
        self.assertEqual([b['status'] for b in self.app.guest(self.table['token'])['batches']],['PREPARING','RECEIVED'])

    def test_staff_progress_guest_visibility_terminal_and_event_history(self):
        bid=self.order()['batch_id']
        for old,new in [('RECEIVED','PREPARING'),('PREPARING','READY'),('READY','SERVED')]:
            self.status(bid,new,old)
            self.assertEqual(self.app.guest(self.table['token'])['batches'][0]['status'],new)
        with self.assertRaises(Problem):self.status(bid,'PREPARING','SERVED')
        c=self.app.connect()
        try:
            events=[dict(r) for r in c.execute('SELECT * FROM OrderBatchEvents WHERE batch_id=? ORDER BY event_id',(bid,))]
            self.assertEqual([e['to_status'] for e in events],['RECEIVED','PREPARING','READY','SERVED'])
            self.assertTrue(all(e['user_id']==2 for e in events[1:]))
        finally:c.close()

    def test_permissions_optimistic_conflict_and_idempotent_transition(self):
        bid=self.order()['batch_id'];body=dict(id=bid,status='PREPARING',expected_status='RECEIVED')
        with self.assertRaises(Problem) as e:self.call('batch_status',body,None)
        self.assertEqual(e.exception.status,401)
        with self.assertRaises(Problem):self.status(bid,'SERVED','RECEIVED')
        first=self.status(bid,'PREPARING','RECEIVED',key='status-repeat-001')
        self.assertEqual(first,self.status(bid,'PREPARING','RECEIVED',key='status-repeat-001'))
        with self.assertRaises(Problem) as e:self.status(bid,'PREPARING','RECEIVED')
        self.assertEqual(e.exception.status,409)

    def test_two_staff_cannot_advance_a_stale_order_twice(self):
        bid=self.order()['batch_id']
        def update(i):
            try:
                self.app.mutate('batch_status',dict(id=bid,status='PREPARING',expected_status='RECEIVED'),self.staff,f'concurrent-batch-{i}')
                return 200
            except Problem as e:return e.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(update,[1,2])),[200,409])

    def test_guest_sees_only_own_batches_and_cannot_write_status(self):
        self.order();other=self.call('open_table',{'table_id':2});self.order(token=other['token'])
        self.assertEqual(len(self.app.guest(self.table['token'])['batches']),1)
        self.assertEqual(len(self.app.snapshot(self.staff)['kitchen_batches']),2)

    def test_pending_remains_visible_after_payment_and_next_day(self):
        bid=self.order()['batch_id']
        self.call('pay',dict(id=self.table['id'],method='CASH',received='200',expected_total=14500))
        self.time+=timedelta(days=1)
        pending=self.app.snapshot(self.staff)['kitchen_batches']
        self.assertEqual(pending[0]['batch_id'],bid);self.assertEqual(pending[0]['is_active'],0)
        self.status(bid,'PREPARING','RECEIVED');self.status(bid,'READY','PREPARING');self.status(bid,'SERVED','READY')
        self.time+=timedelta(days=1)
        self.assertEqual(self.app.snapshot(self.staff)['kitchen_batches'],[])

    def test_invalid_submission_rolls_back_items_and_batch(self):
        with self.assertRaises(Problem):
            self.call('place_order',dict(token=self.table['token'],items=[dict(menu_id=1,quantity=1,expected_price=6500),dict(menu_id=6,quantity=0,expected_price=1500)]),None)
        g=self.app.guest(self.table['token']);self.assertEqual(g['batches'],[]);self.assertEqual(g['items'],[])

    def test_upgrade_preserves_existing_submissions_and_does_not_duplicate(self):
        self.order();self.order()  # Both have identical timestamps and contents.
        c=self.app.connect()
        try:
            c.executescript('DROP TABLE OrderBatchEvents;DROP TABLE OrderBatchItems;DROP TABLE OrderBatches;PRAGMA user_version=2;')
        finally:c.close()
        self.app.initialize();self.app.initialize()
        g=self.app.guest(self.table['token'])
        self.assertEqual(len(g['batches']),2)
        self.assertTrue(all(b['legacy']==1 for b in g['batches']))
        self.assertEqual(sum(len(b['items']) for b in g['batches']),4)
        self.assertEqual(g['order']['total_amount'],29000)
        c=self.app.connect()
        try:self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:c.close()
