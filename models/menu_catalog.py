"""Idempotent, non-destructive import of the owner's photographed menu."""
import hashlib
import json
from config import ROOT
from models.common import require

SEED_ITEMS = [('ข้าวกะเพราหมู','จานเดียว',6500),('ข้าวผัดกุ้ง','จานเดียว',8000),
              ('ต้มยำกุ้ง','กับข้าว',15000),('ไข่เจียว','กับข้าว',5000),
              ('ชาไทยเย็น','เครื่องดื่ม',4000),('น้ำเปล่า','เครื่องดื่ม',1500)]


def read_catalog():
    catalog=json.loads((ROOT/'assets/menu/catalog.json').read_text())
    items=catalog['items'];keys=set()
    for i in items:
        require(i['key'] not in keys,'รหัสเมนูซ้ำในไฟล์นำเข้า');keys.add(i['key'])
        require(isinstance(i['price'],int) and i['price']>=0,'ราคาเมนูต้องเป็นสตางค์จำนวนเต็ม')
        require(i['price']>0 or i['review_note'],'ห้ามนำเข้าราคาศูนย์โดยไม่มีหมายเหตุรอยืนยัน')
    return catalog


def install_menu_catalog(app):
    catalog=read_catalog()
    inserted=0
    with app.transaction() as c:
        if not c.execute("SELECT 1 FROM Settings WHERE key='owner_menu_installed'").fetchone():
            if app.demo:
                for name,category,price in SEED_ITEMS:
                    for r in c.execute('SELECT menu_id FROM MenuItems WHERE name=? AND category=? AND price=?',(name,category,price)).fetchall():
                        mid=r['menu_id']
                        c.execute('UPDATE MenuItems SET is_available=0 WHERE menu_id=?',(mid,))
                        c.execute('INSERT OR IGNORE INTO MenuCatalog VALUES(?,?,?,?)',(f'legacy-demo:{mid}',mid,'legacy-demo',''))
            c.execute("INSERT INTO Settings VALUES('owner_menu_installed',?)",(catalog['version'],))
        for item in catalog['items']:
            if c.execute('SELECT 1 FROM MenuCatalog WHERE source_key=?',(item['key'],)).fetchone():
                continue  # Restart never overwrites a price/status the owner edited.
            mid=c.execute('INSERT INTO MenuItems(name,category,price,is_available) VALUES(?,?,?,?)',
                          (item['name'],item['category'],item['price'],int(not item['review_note']))).lastrowid
            fingerprint=hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            c.execute('INSERT INTO MenuCatalog VALUES(?,?,?,?)',(item['key'],mid,fingerprint,item['review_note']))
            inserted+=1
        if inserted:
            c.execute('INSERT INTO AuditLog(actor,action,entity_id,created_at) VALUES(?,?,?,?)',
                      ('SYSTEM','owner_menu_import',str(inserted),app.stamp()))
    return inserted
