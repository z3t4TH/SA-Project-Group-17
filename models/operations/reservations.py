"""ReservationOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations
from models.entities import Reservation


class ReservationOperations(DomainOperations):
    def reserve(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        name=string(b.get('name')); tel=phone(b.get('phone')); guests=integer(b.get('guests'))
        require(c.execute('SELECT 1 FROM Tables WHERE capacity>=?',(guests,)).fetchone(),'จำนวนคนเกินความจุโต๊ะ กรุณาติดต่อร้าน')
        slots=restaurant.slots(c,guests)
        slot=next((s for s in slots if s['datetime']==b.get('slot')),None)
        require(slot and slot['available'],'รอบที่เลือกเต็มหรือพ้นเวลาแล้ว กรุณาเลือกรอบอื่น',409,alternatives=[s for s in slots if s['available']])
        code='R-'+secrets.token_hex(5).upper()
        rid=c.execute('INSERT INTO Reservations(reservation_code,customer_name,phone_number,reservation_datetime,guest_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(code,name,tel,b['slot'],guests,now,now)).lastrowid
        return dict(id=rid,code=code,message='จองสำเร็จ กรุณาเก็บรหัสไว้เช็คอิน',slot=b['slot'])

    def _lookup_cancel(self,c,a,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        r=one(c,'SELECT * FROM Reservations WHERE reservation_code=? AND phone_number=?',(string(b.get('code'),30).upper(),phone(b.get('phone'))),'ไม่พบการจอง กรุณาตรวจสอบรหัสและเบอร์โทร')
        if a=='lookup':return {'reservation':r}
        require(Reservation.from_row(r).can_cancel(now),'รายการนี้ยกเลิกไม่ได้ เนื่องจากพ้นเวลาหรือสถานะเปลี่ยนแล้ว',409)
        c.execute("UPDATE Reservations SET status='CANCELLED',updated_at=? WHERE reservation_id=?",(now,r['reservation_id']))
        return dict(id=r['reservation_id'],message='ยกเลิกการจองและคืนโควตาแล้ว')

    def lookup(self,c,b,u):
        return self._lookup_cancel(c,'lookup',b,u)

    def cancel(self,c,b,u):
        return self._lookup_cancel(c,'cancel',b,u)

    def _checkin_no_show(self,c,a,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        r=one(c,'SELECT * FROM Reservations WHERE reservation_id=?',(integer(b.get('id'),1,10000000),))
        require(r['status']=='CONFIRMED','รายการจองไม่อยู่ในสถานะรอเช็คอิน',409)
        dt=datetime.fromisoformat(r['reservation_datetime'])
        if a=='no_show':
            require(Reservation.from_row(r).past_grace(restaurant.now()),'ยังไม่พ้นเวลาผ่อนผัน 15 นาที',409)
            c.execute("UPDATE Reservations SET status='NO_SHOW',updated_at=? WHERE reservation_id=?",(now,r['reservation_id']))
        else:
            require(dt.date()==restaurant.now().date(),'เช็คอินได้เฉพาะวันที่จอง',409)
            table=restaurant.assign_table(c,b.get('table_id'),r['guest_count'])['table_id']
            c.execute("UPDATE Reservations SET status='CHECKED_IN',table_id=?,updated_at=? WHERE reservation_id=?",(table,now,r['reservation_id']))
        return dict(id=r['reservation_id'],message='บันทึกการจองแล้ว')

    def checkin(self,c,b,u):
        return self._checkin_no_show(c,'checkin',b,u)

    def no_show(self,c,b,u):
        return self._checkin_no_show(c,'no_show',b,u)
