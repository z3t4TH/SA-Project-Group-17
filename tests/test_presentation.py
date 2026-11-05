"""Verify realistic seeded relationships, repeatability and live-data safeguards."""
import json,sqlite3,tempfile,unittest,hashlib
from pathlib import Path
from models.presentation import prepare,verify,presentation_clock,metadata
from models.restaurant import Restaurant
from models.menu_images import image_manifest
from config import ROOT

class Presentation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'presentation.sqlite3'
    def tearDown(self):self.temp.cleanup()
    def test_three_days_balances_states_and_clock(self):
        result=prepare(self.path)
        self.assertEqual(result['days'],['2026-11-03','2026-11-04','2026-11-05'])
        self.assertEqual(len(result['settlements']),2)
        first,second=result['settlements'];self.assertLess(first['net_profit_loss'],0);self.assertEqual(second['previous_loss'],first['accumulated_loss']);self.assertGreater(second['distributable_profit'],0)
        self.assertEqual(sum(json.loads(second['partner_shares'])),second['distributable_profit'])
        self.assertEqual(set(result['batches']),{'RECEIVED','PREPARING','READY','SERVED'})
        app=Restaurant(self.path,True,presentation_clock(self.path));self.assertEqual(app.today(),'2026-11-05')
        c=app.connect()
        try:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM Orders WHERE is_active=1').fetchone()[0],4)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM Tables WHERE status='AVAILABLE'").fetchone()[0],4)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM MenuCatalog WHERE review_note!=''").fetchone()[0],3)
            self.assertFalse(c.execute('SELECT 1 FROM OrderItems i JOIN MenuCatalog m USING(menu_id) WHERE m.review_note!=\'\'').fetchone())
            self.assertEqual({r[0] for r in c.execute('SELECT payment_method FROM Payments')},{'CASH','MOCK_QR'})
            self.assertGreater(c.execute('SELECT COUNT(*) FROM Orders o WHERE is_active=0 AND total_amount=0 AND NOT EXISTS(SELECT 1 FROM Payments p WHERE p.order_id=o.order_id)').fetchone()[0],0)
        finally:c.close()
    def test_prepare_preserves_interactive_changes_reset_backs_up(self):
        before=prepare(self.path)
        app=Restaurant(self.path,True,presentation_clock(self.path));app.mutate('settings',dict(capacity=31),{'user_id':1,'role':'OWNER'},'presentation-test-setting')
        self.assertEqual(prepare(self.path)['counts'],before['counts'])
        c=app.connect();self.assertEqual(c.execute("SELECT value FROM Settings WHERE key='slot_capacity'").fetchone()[0],'31');c.close()
        prepare(self.path,reset=True)
        saved=list((self.path.parent/'backups').glob('*.sqlite3'));self.assertEqual(len(saved),1)
        c=sqlite3.connect(saved[0]);self.assertEqual(c.execute("SELECT value FROM Settings WHERE key='slot_capacity'").fetchone()[0],'31');c.close()
        self.assertEqual(verify(self.path)['counts'],before['counts'])
    def test_refuses_any_existing_non_presentation_database(self):
        app=Restaurant(self.path,False);app.initialize('testing-live-password')
        for reset in (False,True):
            with self.assertRaises(SystemExit):prepare(self.path,reset=reset)
        self.assertEqual(metadata(self.path)['mode'],'live')
        with self.assertRaises(SystemExit):prepare(self.path.parent/'live.sqlite3')
    def test_skips_monday_and_rejects_closed_anchor(self):
        self.assertEqual(prepare(self.path,'2026-11-03')['days'],['2026-10-31','2026-11-01','2026-11-03'])
        with self.assertRaises(ValueError):prepare(self.path,'2026-11-02',True)
    def test_each_catalog_item_has_a_distinct_licensed_photo(self):
        media=image_manifest();catalog=json.loads((ROOT/'assets/menu/catalog.json').read_text())
        self.assertEqual({x['key'] for x in catalog['items']},set(media['by_key']))
        self.assertEqual(len(media['by_key']),157);self.assertEqual(len(set(media['by_key'].values())),157)
        hashes=set();sources=set()
        for item in json.loads((ROOT/'assets/menu/image-credits.json').read_text()):
            path=ROOT/'assets/menu/images'/item['file'].rsplit('/',1)[-1];blob=path.read_bytes()
            self.assertTrue(blob.startswith(b'\xff\xd8'));self.assertTrue(item['source'].startswith('https://commons.wikimedia.org/'));self.assertTrue(item['author']);self.assertNotIn('NC',item['license']);self.assertNotIn('ND',item['license'])
            digest=hashlib.sha256(blob).hexdigest();self.assertEqual(digest,item['sha256']);self.assertNotIn(digest,hashes);hashes.add(digest)
            self.assertNotIn(item['source'],sources);sources.add(item['source'])
        self.assertTrue((ROOT/'assets/menu/images/placeholder.svg').exists())

    def test_guest_menu_keeps_stable_photo_key_when_owner_renames(self):
        prepare(self.path);app=Restaurant(self.path,True,presentation_clock(self.path))
        c=app.connect()
        try:
            m=dict(c.execute("SELECT m.*,mc.source_key FROM MenuItems m JOIN MenuCatalog mc USING(menu_id) WHERE m.is_available=1 AND mc.review_note='' LIMIT 1").fetchone())
            token=c.execute('SELECT session_token FROM Orders WHERE is_active=1 LIMIT 1').fetchone()[0]
        finally:c.close()
        app.mutate('menu_save',dict(id=m['menu_id'],name='ชื่อใหม่สำหรับทดสอบ',category=m['category'],price=str(m['price']/100),available=True),{'user_id':1,'role':'OWNER'},'image-rename-test')
        changed=next(x for x in app.guest(token)['menu'] if x['menu_id']==m['menu_id'])
        self.assertEqual(changed['catalog_key'],m['source_key']);self.assertIn(changed['catalog_key'],image_manifest()['by_key'])
