import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from service import ROOT, Restaurant, Problem, TZ
from menu_catalog import install_menu_catalog,read_catalog


class OwnerMenu(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=Restaurant(Path(self.tmp.name)/'menu.sqlite3',True,lambda:datetime(2026,10,27,12,tzinfo=TZ))
        self.app.initialize();self.owner={'user_id':1,'role':'OWNER'};self.seq=0

    def tearDown(self):self.tmp.cleanup()

    def call(self,action,body,user=True):
        self.seq+=1
        return self.app.mutate(action,body,self.owner if user else None,f'menu-test-{self.seq:05}')

    def menu_item(self,name):return next(m for m in self.app.snapshot(self.owner)['menu'] if m['name']==name)

    def test_import_is_repeatable_and_preserves_owner_edits(self):
        self.assertEqual(install_menu_catalog(self.app),157)
        m=self.menu_item('ตำไทย')
        self.call('menu_save',dict(id=m['menu_id'],name=m['name'],category=m['category'],price='35',available=False))
        self.assertEqual(install_menu_catalog(self.app),0)
        after=self.menu_item('ตำไทย');self.assertEqual(after['price'],3500);self.assertFalse(after['is_available'])
        self.assertEqual(len(self.app.snapshot(self.owner)['menu']),157)

    def test_guest_menu_has_prices_and_variants_without_legacy_or_pending(self):
        install_menu_catalog(self.app)
        o=self.call('open_table',{'table_id':1});menu=self.app.guest(o['token'])['menu']
        self.assertEqual(len(menu),154)
        names={m['name']:m['price'] for m in menu}
        self.assertNotIn('ข้าวกะเพราหมู',names);self.assertNotIn('ปลาดุกย่าง',names)
        self.assertEqual(names['ตำไทย'],3000);self.assertEqual(names['ตำไทยปู'],4000)
        self.assertEqual(names['ข้าวผัดปู (กลาง)'],10000)
        self.assertEqual(names['เมี่ยงคำ (ใหญ่)'],8000)
        self.assertEqual(names['ไข่เจียวกุ้งสับ'],5000)
        self.assertEqual(names['ข้าวไข่เจียวกุ้ง'],4000)

    def test_pending_price_needs_explicit_confirmation_before_ordering(self):
        install_menu_catalog(self.app);m=self.menu_item('ปลาดุกย่าง')
        body=dict(id=m['menu_id'],name=m['name'],category=m['category'],price='50',available=True)
        with self.assertRaises(Problem):self.call('menu_save',body)
        with self.assertRaises(Problem):self.call('menu_save',dict(body,price='0',review_confirmed=True))
        o=self.call('open_table',{'table_id':1})
        # Even a mistakenly toggled DB availability flag cannot sell a pending item.
        with self.app.transaction() as c:c.execute('UPDATE MenuItems SET is_available=1 WHERE menu_id=?',(m['menu_id'],))
        with self.assertRaises(Problem):self.call('place_order',dict(token=o['token'],items=[dict(menu_id=m['menu_id'],quantity=1,expected_price=0)]),False)
        self.call('menu_save',dict(body,review_confirmed=True))
        self.assertEqual(self.menu_item('ปลาดุกย่าง')['review_note'],'')
        self.call('place_order',dict(token=o['token'],items=[dict(menu_id=m['menu_id'],quantity=1,expected_price=5000)]),False)
        install_menu_catalog(self.app)
        self.assertEqual(self.menu_item('ปลาดุกย่าง')['price'],5000)

    def test_owner_menu_order_to_cash_payment(self):
        install_menu_catalog(self.app);o=self.call('open_table',{'table_id':1})
        tam=self.menu_item('ตำไทย');miang=self.menu_item('เมี่ยงคำ (ใหญ่)')
        self.call('place_order',dict(token=o['token'],items=[dict(menu_id=tam['menu_id'],quantity=2,expected_price=3000,note='เผ็ดน้อย'),dict(menu_id=miang['menu_id'],quantity=1,expected_price=8000)]),False)
        pay=self.call('pay',dict(id=o['id'],method='CASH',expected_total=14000,received='150'))
        self.assertEqual(pay['change'],1000)
        bill=self.app.bill(self.owner,o['id']);self.assertEqual(bill['order']['total_amount'],14000)
        self.assertEqual([i['name_snapshot'] for i in bill['items']],['ตำไทย','เมี่ยงคำ (ใหญ่)'])

    def test_migration_preserves_existing_menu_and_upgrades_version_one(self):
        path=Path(self.tmp.name)/'old.sqlite3';c=sqlite3.connect(path)
        c.executescript((ROOT/'migrations/001_initial.sql').read_text())
        c.execute("INSERT INTO MenuItems(name,category,price,is_available) VALUES('เมนูเดิมของเจ้าของ','เดิม',12300,1)");c.commit();c.close()
        app=Restaurant(path,True);app.initialize();install_menu_catalog(app)
        c=app.connect()
        try:
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],3)
            self.assertEqual(c.execute("SELECT price FROM MenuItems WHERE name='เมนูเดิมของเจ้าของ'").fetchone()[0],12300)
            self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
        finally:c.close()

    def test_only_owner_pending_entries_are_held(self):
        catalog=read_catalog();pending=[i['name'] for i in catalog['items'] if i['review_note']]
        self.assertCountEqual(pending,['ปลาดุกย่าง','ซุปหน่อไม้','ไส้กรอก/ไส้อั่ว'])


if __name__=='__main__':unittest.main(verbosity=2)
