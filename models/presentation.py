"""Repeatable presentation fixtures, always isolated from demo/live restaurant data."""
from datetime import date,datetime,timedelta
from pathlib import Path
import json,os,sqlite3,tempfile
from config import ROOT,TZ
from database_tools import database_lock,backup_database,timestamp
from models.restaurant import Restaurant
from models.menu_catalog import install_menu_catalog

VERSION='presentation-v1'
DEFAULT_DATE='2026-11-05'

def metadata(path):
    path=Path(path)
    if not path.exists():return {}
    c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return dict(c.execute("SELECT key,value FROM Settings WHERE key LIKE 'presentation_%' OR key='mode'")) if 'Settings' in tables else {}
    finally:c.close()

def presentation_clock(path):
    m=metadata(path)
    if m.get('presentation_seed_version')!=VERSION or m.get('mode')!='demo':raise SystemExit('ฐานนี้ไม่ใช่ Presentation Demo ที่รองรับ')
    stamp=datetime.fromisoformat(m['presentation_now'])
    return lambda:stamp

def verify(path):
    if metadata(path).get('presentation_seed_version')!=VERSION:raise SystemExit('ไม่ใช่ฐาน Presentation Demo')
    c=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    try:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert not c.execute('SELECT 1 FROM Orders o WHERE total_amount!=COALESCE((SELECT SUM(quantity*item_price) FROM OrderItems i WHERE i.order_id=o.order_id),0)').fetchone()
        assert not c.execute('SELECT 1 FROM Payments p JOIN Orders o USING(order_id) WHERE p.total_paid!=o.total_amount OR p.amount_received!=p.total_paid+p.change_amount OR o.is_active!=0').fetchone()
        settlements=[dict(r) for r in c.execute('SELECT * FROM DailySettlements ORDER BY settlement_date')]
        from models.entities import DailySettlement
        carried=0
        for s in settlements:
            total=c.execute('SELECT COALESCE(SUM(total_paid),0) FROM Payments WHERE settlement_id=?',(s['settlement_id'],)).fetchone()[0]
            labor=c.execute('SELECT COALESCE(SUM(wage_amount),0) FROM DailyWages WHERE settlement_id=?',(s['settlement_id'],)).fetchone()[0]
            cash=c.execute("SELECT COALESCE(SUM(total_paid),0) FROM Payments WHERE settlement_id=? AND payment_method='CASH'",(s['settlement_id'],)).fetchone()[0]
            assert cash==s['expected_cash'] and s['actual_cash']-cash==s['cash_difference'] and s['previous_loss']==carried
            carried=s['accumulated_loss']
            a=DailySettlement.compute(total,s['material_cost'],labor,s['previous_loss'])
            assert total==s['total_sales'] and labor==s['labor_cost'] and a.net==s['net_profit_loss'] and a.next_loss==s['accumulated_loss'] and a.distributable==s['distributable_profit'] and list(a.shares)==json.loads(s['partner_shares'])
        m=metadata(path)
        current_closed=bool(c.execute('SELECT 1 FROM DailySettlements WHERE settlement_date=?',(m['presentation_date'],)).fetchone())
        return dict(current_day_closed=current_closed,date=m['presentation_date'],days=json.loads(m['presentation_days']),integrity='ok',foreign_key_errors=0,settlements=settlements,counts={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['Reservations','Queues','Orders','OrderItems','OrderBatches','Payments','DailyWages']},batches=dict(c.execute('SELECT status,COUNT(*) FROM OrderBatches GROUP BY status')))
    finally:c.close()

def _seed(path,anchor):
    current=date.fromisoformat(anchor)
    if current.weekday()==0:raise ValueError('วันสาธิตต้องเป็นวันเปิดร้าน อังคาร–อาทิตย์')
    days=[current];cursor=current
    while len(days)<3:
        cursor-=timedelta(days=1)
        if cursor.weekday()!=0:days.insert(0,cursor)
    now=[datetime.combine(days[0],datetime.min.time(),TZ).replace(hour=10)]
    app=Restaurant(path,True,lambda:now[0]);app.initialize();install_menu_catalog(app)
    owner={'user_id':1,'role':'OWNER'};staff={'user_id':2,'role':'STAFF'};seq=0
    def at(day,hour,minute=0):now[0]=datetime.combine(day,datetime.min.time(),TZ).replace(hour=hour,minute=minute)
    def call(action,body=None,user=staff):
        nonlocal seq
        seq+=1;return app.mutate(action,body or {},user,f'presentation-seed-{seq:05}')
    c=app.connect()
    try:menu=[dict(r) for r in c.execute("SELECT m.* FROM MenuItems m JOIN MenuCatalog mc USING(menu_id) WHERE m.is_available=1 AND mc.review_note='' AND m.price>0 ORDER BY m.menu_id")];staff_ids=[str(r[0]) for r in c.execute('SELECT staff_id FROM Staff WHERE is_active=1')]
    finally:c.close()
    def select(category):return next(x for x in menu if x['category']==category)
    dishes=[select(x) for x in ['ส้มตำ','ยำ','ข้าว','ย่าง','เมี่ยงคำ','ต้มยำและต้มแซ่บ']]
    def order(o,choice,qty=2,note='เผ็ดน้อย · ข้อมูลสมมุติ'):
        return call('place_order',dict(token=o['token'],items=[dict(menu_id=choice['menu_id'],quantity=qty,expected_price=choice['price'],note=note)]),None)
    def advance(batch,stage=3):
        states=['RECEIVED','PREPARING','READY','SERVED']
        for i in range(stage):call('batch_status',dict(id=batch['batch_id'],expected_status=states[i],status=states[i+1]))
    def finish(o,method='CASH'):
        total=app.bill(staff,o['id'])['order']['total_amount']
        return call('pay',dict(id=o['id'],expected_total=total,method=method,received=f'{(total+10000)/100:.2f}',confirmed=True))
    def reservation_examples(day,final=False):
        at(day,10)
        def reserve(label,hour):return call('reserve',dict(name='ลูกค้าสาธิต '+label,phone='0000000000',guests=2,slot=datetime.combine(day,datetime.min.time(),TZ).replace(hour=hour).isoformat(timespec='seconds')),None)
        cancel=reserve('ยกเลิก',12);call('cancel',dict(code=cancel['code'],phone='0000000000'),None)
        missed=reserve('ไม่มาตามนัด',11);at(day,11,20);call('no_show',dict(id=missed['id']),owner)
        checked=reserve('เช็คอิน',12);call('checkin',dict(id=checked['id'],table_id=1));o=call('open_table',dict(table_id=1));batch=order(o,dishes[0]);advance(batch);finish(o)
        if final:reserve('รอเช็คอิน',14);reserve('จองบ่าย',15)
        q=call('queue_create',dict(name='กลุ่มสาธิต เข้าที่นั่ง',guests=2,phone='0000000000'));call('queue_call',dict(id=q['id']));call('queue_seat',dict(id=q['id'],table_id=2));o=call('open_table',dict(table_id=2));b=order(o,dishes[2]);advance(b);finish(o,'MOCK_QR')
        q=call('queue_create',dict(name='กลุ่มสาธิต ข้ามคิว',guests=2))
        for _ in range(3):call('queue_call',dict(id=q['id']))
        call('queue_skip',dict(id=q['id']))
        q=call('queue_create',dict(name='กลุ่มสาธิต ยกเลิกคิว',guests=2));call('queue_cancel',dict(id=q['id']))
    for day_index,day in enumerate(days):
        reservation_examples(day,day==current)
        at(day,12)
        for i in range(6+day_index*2):
            o=call('open_table',dict(table_id=(i%6)+1));b=order(o,dishes[i%len(dishes)],3+day_index);advance(b)
            b=order(o,dishes[(i+2)%len(dishes)],2,note='แยกน้ำจิ้ม · ข้อมูลสมมุติ');advance(b);paid=finish(o,'CASH' if i%2==0 else 'MOCK_QR')
            call('print_status',dict(id=paid['job_id'],status='PRINTED' if i%3 else 'FAILED'))
        o=call('open_table',dict(table_id=8));call('close_empty',dict(id=o['id']))
        if day!=current:
            at(day,16,15);sales=app.snapshot(owner)['sales'];labor=125000
            material=max(0,sales['total']+50000-labor) if day_index==0 else 30000
            call('settle',dict(material=f'{material/100:.2f}',actual_cash=f'{sales["cash"]/100:.2f}',staff_ids=staff_ids),owner)
    at(current,13,30)
    # Four live tables, one batch per status; T01 also demonstrates a second submission.
    for table,stage in [(1,0),(2,1),(3,2),(4,3)]:
        o=call('open_table',dict(table_id=table));b=order(o,dishes[table%len(dishes)]);advance(b,stage)
        if table==1:order(o,dishes[4],1,'ไม่ใส่พริก · รอบที่สอง')
    q=call('queue_create',dict(name='กลุ่มสาธิต รอเรียก',guests=3));call('queue_call',dict(id=q['id']))
    call('queue_create',dict(name='กลุ่มสาธิต Walk-in ใหม่',guests=2))
    c=app.connect()
    try:
        c.executemany('INSERT INTO Settings(key,value) VALUES(?,?)',[
            ('presentation_seed_version',VERSION),('presentation_date',current.isoformat()),('presentation_now',now[0].isoformat(timespec='seconds')),('presentation_days',json.dumps([d.isoformat() for d in days]))]);c.commit()
    finally:c.close()
    return verify(path)

def prepare(path=None,anchor=DEFAULT_DATE,reset=False):
    path=Path(path or ROOT/'data/presentation.sqlite3')
    if path.name!='presentation.sqlite3':raise SystemExit('สร้างข้อมูลได้เฉพาะไฟล์ presentation.sqlite3 เท่านั้น')
    day=date.fromisoformat(anchor)
    if day.weekday()==0:raise ValueError('วันสาธิตต้องไม่ใช่วันจันทร์')
    with database_lock(path):
        old=metadata(path)
        if path.exists():
            if old.get('mode')!='demo' or old.get('presentation_seed_version')!=VERSION:raise SystemExit('ไม่เขียนทับฐานที่ไม่มีเครื่องหมาย Presentation Demo')
            if not reset:
                if old.get('presentation_date')!=anchor:raise SystemExit('ต้องใช้ reset-presentation เพื่อเปลี่ยนวัน โดยจะสำรองฐานเดิมก่อน')
                return verify(path)
            backup_database(path,path.parent/'backups'/('presentation-before-reset-'+timestamp()+'.sqlite3'))
        # Construct and verify before replacing; never leave a half-seeded database.
        with tempfile.TemporaryDirectory(dir=path.parent,prefix='presentation-build-') as folder:
            fresh=Path(folder)/'presentation.sqlite3';result=_seed(fresh,anchor)
            c=sqlite3.connect(fresh);c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close()
            os.replace(fresh,path)
        return result
