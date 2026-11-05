"""DocumentOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations


class DocumentOperations(DomainOperations):
    def print_status(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        jid=integer(b.get('id'),1,10000000);status=b.get('status');require(status in ('PRINTED','FAILED','PENDING'),'สถานะพิมพ์ไม่ถูกต้อง')
        one(c,'SELECT job_id FROM PrintJobs WHERE job_id=?',(jid,))
        c.execute('UPDATE PrintJobs SET status=?,attempts=attempts+1 WHERE job_id=?',(status,jid))
        return dict(id=jid,message='บันทึกสถานะการพิมพ์แล้ว')
