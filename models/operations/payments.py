"""PaymentOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations
from models.entities import Order,Payment


class PaymentOperations(DomainOperations):
    def pay(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        o=one(c,'SELECT * FROM Orders WHERE order_id=?',(integer(b.get('id'),1,10000000),))
        require(Order.from_row(o).is_open(),'บิลนี้รับชำระและปิดแล้ว',409)
        require(o['total_amount']>0,'ไม่พบรายการสั่งอาหารในบิลนี้',409)
        require(b.get('expected_total')==o['total_amount'],'ยอดบิลเปลี่ยนแล้ว กรุณาตรวจสอบบิลอีกครั้ง',409)
        method=b.get('method');require(method in ('CASH','MOCK_QR'),'ช่องทางชำระไม่ถูกต้อง')
        if method=='MOCK_QR':
            require(b.get('confirmed') is True,'พนักงานต้องยืนยันตรวจสอบการชำระจำลองก่อน',409)
            received=o['total_amount']
        else:received=money(b.get('received'))
        change=Payment.compute_change(o['total_amount'],received)
        pid=c.execute('INSERT INTO Payments(payment_method,total_paid,amount_received,change_amount,payment_time,order_id,received_by) VALUES(?,?,?,?,?,?,?)',(method,o['total_amount'],received,change,now,o['order_id'],u['user_id'])).lastrowid
        c.execute('UPDATE Orders SET is_active=0,closed_at=? WHERE order_id=?',(now,o['order_id']))
        c.execute("UPDATE Tables SET status='AVAILABLE' WHERE table_id=?",(o['table_id'],))
        job=restaurant.print_job(c,'RECEIPT',dict(payment_id=pid,order_id=o['order_id']))
        return dict(id=pid,job_id=job,change=change,message='รับชำระสำเร็จและคืนโต๊ะว่างแล้ว')

    def close_empty(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        o=one(c,'SELECT * FROM Orders WHERE order_id=?',(integer(b.get('id'),1,10000000),))
        require(Order.from_row(o).can_close_empty(),'ปิดโดยไม่รับเงินได้เฉพาะบิลยอดศูนย์',409)
        c.execute('UPDATE Orders SET is_active=0,closed_at=? WHERE order_id=?',(now,o['order_id']))
        c.execute("UPDATE Tables SET status='AVAILABLE' WHERE table_id=?",(o['table_id'],))
        return dict(id=o['order_id'],message='ปิดโต๊ะยอดศูนย์แล้ว ไม่มีการรับเงิน')
