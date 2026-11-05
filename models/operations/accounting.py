"""AccountingOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations
from models.entities import Staff,DailySettlement,DailyWage


class AccountingOperations(DomainOperations):
    def settle(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        restaurant.open_day(c)
        require(not c.execute("SELECT 1 FROM Tables WHERE status!='AVAILABLE'").fetchone() and not c.execute('SELECT 1 FROM Orders WHERE is_active=1').fetchone(),'ยังมีโต๊ะเปิดหรือโต๊ะที่จัดสรรไว้ กรุณาปิดให้ครบก่อน',409)
        require(not c.execute("SELECT 1 FROM Queues WHERE service_date=? AND status IN ('WAITING','CALLED')",(restaurant.today(),)).fetchone(),'กรุณาจัดการคิวที่ยังรอให้ครบก่อนปิดบัญชี',409)
        require(not c.execute("SELECT 1 FROM Reservations WHERE substr(reservation_datetime,1,10)=? AND status='CONFIRMED'",(restaurant.today(),)).fetchone(),'ยังมีการจองวันนี้ที่รอเช็คอิน กรุณาจัดการก่อนปิดบัญชี',409)
        staff=b.get('staff_ids');require(isinstance(staff,list) and len(staff)==len(set(map(str,staff))),'รายชื่อพนักงานซ้ำหรือไม่ถูกต้อง')
        wages=[]
        for sid in staff:wages.append(one(c,'SELECT * FROM Staff WHERE staff_id=? AND is_active=1',(integer(sid,1,100000),)))
        material=money(b.get('material'));actual=money(b.get('actual_cash'));sales=restaurant.sales(c,restaurant.today());labor=sum(Staff.from_row(s).payable_wage() for s in wages)
        note=b.get('difference_note','');require(isinstance(note,str) and len(note)<=500,'หมายเหตุยาวเกิน 500 ตัวอักษร')
        require(actual==sales['cash'] or note.strip(),'เงินสดจริงไม่ตรงยอด กรุณาระบุเหตุผลส่วนต่าง')
        prev=c.execute('SELECT accumulated_loss,settlement_date FROM DailySettlements ORDER BY settlement_date DESC LIMIT 1').fetchone()
        require(not prev or prev['settlement_date']<restaurant.today(),'วันที่ระบบถอยหลังกว่ารอบบัญชีล่าสุด',409)
        loss=prev['accumulated_loss'] if prev else 0
        allocation=DailySettlement.compute(sales['total'],material,labor,loss)
        net=allocation.net;dist=allocation.distributable;new_loss=allocation.next_loss;shares=list(allocation.shares)
        sid=c.execute('INSERT INTO DailySettlements(settlement_date,total_sales,material_cost,labor_cost,net_profit_loss,previous_loss,accumulated_loss,distributable_profit,partner_shares,expected_cash,actual_cash,cash_difference,difference_note,closed_by,closed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(restaurant.today(),sales['total'],material,labor,net,loss,new_loss,dist,json.dumps(shares),sales['cash'],actual,actual-sales['cash'],note,u['user_id'],now)).lastrowid
        for s in wages:c.execute('INSERT INTO DailyWages(settlement_id,staff_id,name_snapshot,wage_amount,recorded_at) VALUES(?,?,?,?,?)',DailyWage.for_staff(Staff.from_row(s),sid,now).insert_values())
        c.execute('UPDATE Payments SET settlement_id=? WHERE substr(payment_time,1,10)=? AND settlement_id IS NULL',(sid,restaurant.today()))
        return dict(id=sid,message='ปิดบัญชีและบันทึกการจัดสรรแล้ว',shares=shares)
