"""AdministrationOperations: persistent business operations inside an existing transaction."""
import re
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations


class AdministrationOperations(DomainOperations):
    def settings(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        capacity=integer(b.get('capacity'),1,200)
        max_used=c.execute("SELECT COALESCE(MAX(n),0) FROM (SELECT SUM(guest_count) n FROM Reservations WHERE status IN ('CONFIRMED','CHECKED_IN') AND reservation_datetime>=? GROUP BY reservation_datetime)",(now,)).fetchone()[0]
        require(capacity>=max_used,'โควตาใหม่ต่ำกว่าที่จองแล้ว',409)
        c.execute("UPDATE Settings SET value=? WHERE key='slot_capacity'",(str(capacity),))
        return {'message':'บันทึกโควตาที่นั่งแล้ว'}

    def table_save(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        name=string(b.get('number'),10);cap=integer(b.get('capacity'))
        if b.get('id'):
            tid=integer(b['id'],1,100000);t=one(c,'SELECT * FROM Tables WHERE table_id=?',(tid,))
            require(t['status']=='AVAILABLE','แก้ไขได้เฉพาะโต๊ะว่าง',409)
            c.execute('UPDATE Tables SET table_number=?,capacity=? WHERE table_id=?',(name,cap,tid))
        else:tid=c.execute('INSERT INTO Tables(table_number,capacity) VALUES(?,?)',(name,cap)).lastrowid
        return dict(id=tid,message='บันทึกโต๊ะแล้ว')

    def staff_save(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        name=string(b.get('name'));role=string(b.get('role'),50);rate=money(b.get('rate'));active=b.get('active',True)
        require(isinstance(active,bool),'สถานะพนักงานไม่ถูกต้อง')
        if b.get('id'):
            sid=integer(b['id'],1,100000);one(c,'SELECT staff_id FROM Staff WHERE staff_id=?',(sid,))
            c.execute('UPDATE Staff SET name=?,role=?,daily_rate=?,is_active=? WHERE staff_id=?',(name,role,rate,int(active),sid))
        else:sid=c.execute('INSERT INTO Staff(name,role,daily_rate) VALUES(?,?,?)',(name,role,rate)).lastrowid
        return dict(id=sid,message='บันทึกพนักงานแล้ว')

    def user_save(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        username=string(b.get('username'),40);password=string(b.get('password'),200);name=string(b.get('name'));role=b.get('role')
        require(re.fullmatch('[a-zA-Z0-9_]+',username) and len(password)>=10 and role in ('OWNER','STAFF'),'ชื่อบัญชีใช้ a-z 0-9 _ และรหัสผ่านอย่างน้อย 10 ตัวอักษร')
        uid=c.execute('INSERT INTO Users(username,password_hash,role,name) VALUES(?,?,?,?)',(username,password_hash(password),role,name)).lastrowid
        return dict(id=uid,message='สร้างบัญชีแล้ว')
