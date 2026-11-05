"""QueueOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations
from models.entities import Queue


class QueueOperations(DomainOperations):
    def queue_create(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        guests=integer(b.get('guests'));tel=phone(b.get('phone',''),True);name=string(b.get('name','ลูกค้า Walk-in'))
        require(c.execute('SELECT 1 FROM Tables WHERE capacity>=?',(guests,)).fetchone(),'จำนวนคนเกินความจุโต๊ะ')
        n=c.execute('SELECT COALESCE(MAX(queue_number),0)+1 FROM Queues WHERE service_date=?',(restaurant.today(),)).fetchone()[0]
        qid=c.execute('INSERT INTO Queues(queue_number,service_date,customer_name,phone_number,guest_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(n,restaurant.today(),name,tel,guests,now,now)).lastrowid
        job=restaurant.print_job(c,'QUEUE',dict(id=qid,number=n,guests=guests,date=restaurant.today()))
        return dict(id=qid,job_id=job,message=f'ออกบัตรคิว Q{n:03} แล้ว')

    def _queue_call_queue_skip_queue_seat_queue_cancel(self,c,a,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        q=one(c,'SELECT * FROM Queues WHERE queue_id=?',(integer(b.get('id'),1,10000000),))
        require(q['service_date']==restaurant.today() and q['status'] in ('WAITING','CALLED'),'คิวนี้ดำเนินการไม่ได้แล้ว',409)
        status=q['status'];count=q['call_count'];table=None
        if a=='queue_call':
            require(Queue.from_row(q).can_call_again(),'เรียกครบ 3 ครั้งแล้ว กรุณาจัดโต๊ะหรือข้ามคิว',409)
            first=c.execute("SELECT queue_id FROM Queues WHERE service_date=? AND status='WAITING' ORDER BY queue_number LIMIT 1",(restaurant.today(),)).fetchone()
            require(status=='CALLED' or (first and first[0]==q['queue_id']),'กรุณาเรียกคิวที่รออยู่ก่อนหน้า',409)
            status='CALLED';count+=1
        elif a=='queue_skip':
            require(Queue.from_row(q).can_skip(),'ต้องเรียกครบ 3 ครั้งก่อนข้ามคิว',409);status='SKIPPED'
        elif a=='queue_cancel':status='CANCELLED'
        else:
            require(status=='CALLED','กรุณาเรียกคิวก่อนจัดโต๊ะ',409)
            table=restaurant.assign_table(c,b.get('table_id'),q['guest_count'])['table_id'];status='SEATED'
        c.execute('UPDATE Queues SET status=?,call_count=?,table_id=?,updated_at=? WHERE queue_id=?',(status,count,table,now,q['queue_id']))
        return dict(id=q['queue_id'],message='บันทึกคิวแล้ว')

    def queue_call(self,c,b,u):
        return self._queue_call_queue_skip_queue_seat_queue_cancel(c,'queue_call',b,u)

    def queue_skip(self,c,b,u):
        return self._queue_call_queue_skip_queue_seat_queue_cancel(c,'queue_skip',b,u)

    def queue_seat(self,c,b,u):
        return self._queue_call_queue_skip_queue_seat_queue_cancel(c,'queue_seat',b,u)

    def queue_cancel(self,c,b,u):
        return self._queue_call_queue_skip_queue_seat_queue_cancel(c,'queue_cancel',b,u)
