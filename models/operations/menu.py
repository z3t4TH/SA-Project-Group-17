"""MenuOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations


class MenuOperations(DomainOperations):
    def menu_save(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        name=string(b.get('name'),150);cat=string(b.get('category'),50);price=money(b.get('price'));available=b.get('available')
        require(isinstance(available,bool),'สถานะเมนูไม่ถูกต้อง')
        if b.get('id'):
            mid=integer(b['id'],1,1000000);one(c,'SELECT menu_id FROM MenuItems WHERE menu_id=?',(mid,))
            review=c.execute('SELECT review_note FROM MenuCatalog WHERE menu_id=?',(mid,)).fetchone()
            if review and review['review_note']:
                if b.get('review_confirmed') is True:
                    require(price>0,'กรุณาระบุราคาจริงที่ยืนยันแล้วก่อนเปิดรายการนี้')
                    c.execute("UPDATE MenuCatalog SET review_note='' WHERE menu_id=?",(mid,))
                else:
                    require(not available,'ต้องยืนยันราคาจากเจ้าของร้านก่อนเปิดขายรายการนี้',409)
            c.execute('UPDATE MenuItems SET name=?,category=?,price=?,is_available=? WHERE menu_id=?',(name,cat,price,int(available),mid))
        else:mid=c.execute('INSERT INTO MenuItems(name,category,price,is_available) VALUES(?,?,?,?)',(name,cat,price,int(available))).lastrowid
        return dict(id=mid,message='บันทึกเมนูแล้ว')
