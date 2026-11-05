"""OrderOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations
from models.entities import Table,MenuItem,Order,OrderItem,OrderBatch


class OrderOperations(DomainOperations):
    def open_table(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        t=one(c,'SELECT * FROM Tables WHERE table_id=?',(integer(b.get('table_id'),1,100000),))
        require(Table.from_row(t).can_open(),'โต๊ะนี้เปิดใช้งานอยู่แล้ว',409)
        token=secrets.token_urlsafe(24)
        c.execute("UPDATE Tables SET status='OCCUPIED' WHERE table_id=?",(t['table_id'],))
        oid=c.execute('INSERT INTO Orders(session_token,opened_at,table_id) VALUES(?,?,?)',(token,now,t['table_id'])).lastrowid
        job=restaurant.print_job(c,'SESSION',dict(order_id=oid,token=token,table_number=t['table_number']))
        return dict(id=oid,token=token,job_id=job,message='เปิดโต๊ะและสร้าง QR แล้ว')

    def place_order(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        o=one(c,'SELECT * FROM Orders WHERE session_token=? AND is_active=1',(str(b.get('token','')),),'QR นี้หมดอายุหรือโต๊ะปิดแล้ว')
        cart=b.get('items');require(isinstance(cart,list) and 1<=len(cart)<=50,'กรุณาเลือกอาหาร 1–50 รายการ')
        prepared=[];item_ids=[]
        for item in cart:
            require(isinstance(item,dict),'รายการอาหารไม่ถูกต้อง')
            m=one(c,'SELECT * FROM MenuItems WHERE menu_id=?',(integer(item.get('menu_id'),1,1000000),))
            require(MenuItem.from_row(m).can_order(),f"{m['name']} หมดแล้ว กรุณาลบออกจากตะกร้า",409)
            review=c.execute('SELECT review_note FROM MenuCatalog WHERE menu_id=?',(m['menu_id'],)).fetchone()
            require(not review or not review['review_note'],'รายการนี้รอยืนยันราคาจากร้าน ยังสั่งไม่ได้',409)
            require(MenuItem.from_row(m).matches_price(item.get('expected_price')),f"ราคา {m['name']} เปลี่ยนแล้ว กรุณารีเฟรชเมนู",409)
            qty=integer(item.get('quantity'),1,99);note=item.get('note','')
            require(isinstance(note,str) and len(note)<=255,'หมายเหตุยาวเกิน 255 ตัวอักษร')
            prepared.append(OrderItem(order_item_id=None,quantity=qty,item_price=m['price'],name_snapshot=m['name'],note=note,ordered_at=now,order_id=o['order_id'],menu_id=m['menu_id']).kitchen_item())
            item_ids.append(c.execute('INSERT INTO OrderItems(quantity,item_price,name_snapshot,note,ordered_at,order_id,menu_id) VALUES(?,?,?,?,?,?,?)',(qty,m['price'],m['name'],note,now,o['order_id'],m['menu_id'])).lastrowid)
        total=c.execute('SELECT SUM(quantity*item_price) FROM OrderItems WHERE order_id=?',(o['order_id'],)).fetchone()[0]
        c.execute('UPDATE Orders SET total_amount=? WHERE order_id=?',(total,o['order_id']))
        table=one(c,'SELECT table_number FROM Tables WHERE table_id=?',(o['table_id'],))
        job=restaurant.print_job(c,'KITCHEN',dict(order_id=o['order_id'],table_number=table['table_number'],items=prepared))
        batch_id=restaurant._create_batch(c,o['order_id'],item_ids,now,job)
        return dict(id=o['order_id'],batch_id=batch_id,message='ส่งออร์เดอร์ให้ร้านแล้ว ติดตามสถานะได้ด้านล่าง',total=total,job_id=job)

    def batch_status(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        batch=one(c,'SELECT * FROM OrderBatches WHERE batch_id=?',(integer(b.get('id'),1,100000000),))
        require(b.get('expected_status')==batch['status'],'สถานะออร์เดอร์เปลี่ยนแล้ว กรุณาอัปเดตก่อนกดอีกครั้ง',409)
        target=OrderBatch.from_row(batch).next_status()
        require(target and b.get('status')==target,'เปลี่ยนสถานะได้ตามลำดับ รับออร์เดอร์ → กำลังทำ → พร้อมเสิร์ฟ → เสิร์ฟแล้ว',409)
        c.execute('UPDATE OrderBatches SET status=?,updated_at=?,updated_by=? WHERE batch_id=?',(target,now,u['user_id'],batch['batch_id']))
        c.execute('INSERT INTO OrderBatchEvents(batch_id,from_status,to_status,user_id,created_at) VALUES(?,?,?,?,?)',(batch['batch_id'],batch['status'],target,u['user_id'],now))
        return dict(id=batch['batch_id'],status=target,message='อัปเดตสถานะออร์เดอร์แล้ว')
