"""Typed domain entities with business rules used by the running application.

Money is integer satang. Relationships are persisted with IDs, not invented
in-memory ownership or delete-cascades. Draft primary keys may be None.
"""
from __future__ import annotations
from dataclasses import dataclass,fields,asdict
from datetime import datetime,timedelta
from models.common import require


class EntityRecord:
    @classmethod
    def from_row(cls,row):
        data=dict(row)
        return cls(**{f.name:data[f.name] for f in fields(cls)})

    def to_dict(self)->dict:
        return asdict(self)


@dataclass(frozen=True)
class SettlementAmounts:
    net:int
    next_loss:int
    distributable:int
    shares:tuple[int,int,int,int]


@dataclass(frozen=True)
class Table(EntityRecord):
    table_id:int|None
    table_number:str
    capacity:int
    status:str

    def can_assign(self,guests:int)->bool:
        return self.status=='AVAILABLE' and self.capacity>=guests

    def can_open(self)->bool:
        return self.status in ('AVAILABLE','HELD')


@dataclass(frozen=True)
class Reservation(EntityRecord):
    reservation_id:int|None
    reservation_code:str
    customer_name:str
    phone_number:str
    reservation_datetime:str
    guest_count:int
    status:str
    table_id:int|None
    created_at:str
    updated_at:str

    def can_cancel(self,now:str)->bool:
        return self.status=='CONFIRMED' and self.reservation_datetime>now

    def past_grace(self,now:datetime,minutes:int=15)->bool:
        return now>datetime.fromisoformat(self.reservation_datetime)+timedelta(minutes=minutes)


@dataclass(frozen=True)
class Queue(EntityRecord):
    queue_id:int|None
    queue_number:int
    service_date:str
    customer_name:str
    phone_number:str
    guest_count:int
    status:str
    call_count:int
    table_id:int|None
    created_at:str
    updated_at:str

    def can_skip(self)->bool:
        return self.call_count>=3

    def can_call_again(self)->bool:
        return self.call_count<3


@dataclass(frozen=True)
class MenuItem(EntityRecord):
    menu_id:int|None
    name:str
    category:str
    price:int
    is_available:int

    def can_order(self)->bool:
        return self.is_available==1

    def matches_price(self,expected_price:int)->bool:
        return self.price==expected_price


@dataclass(frozen=True)
class Order(EntityRecord):
    order_id:int|None
    session_token:str
    opened_at:str
    closed_at:str|None
    total_amount:int
    is_active:int
    table_id:int

    def is_open(self)->bool:
        return self.is_active==1

    def can_close_empty(self)->bool:
        return self.is_open() and self.total_amount==0


@dataclass(frozen=True)
class OrderItem(EntityRecord):
    order_item_id:int|None
    quantity:int
    item_price:int
    name_snapshot:str
    note:str
    ordered_at:str
    order_id:int
    menu_id:int

    def line_total(self)->int:
        return self.quantity*self.item_price

    def kitchen_item(self)->dict:
        return dict(name=self.name_snapshot,quantity=self.quantity,price=self.item_price,note=self.note)


@dataclass(frozen=True)
class Payment(EntityRecord):
    payment_id:int|None
    payment_method:str
    total_paid:int
    amount_received:int
    change_amount:int
    payment_time:str
    order_id:int
    settlement_id:int|None
    received_by:int

    @staticmethod
    def compute_change(total:int,received:int)->int:
        require(received>=total,'เงินสดที่รับไม่เพียงพอ',409)
        return received-total

    def is_cash(self)->bool:
        return self.payment_method=='CASH'


@dataclass(frozen=True)
class Staff(EntityRecord):
    staff_id:int|None
    name:str
    role:str
    daily_rate:int
    phone_number:str
    is_active:int

    def payable_wage(self)->int:
        return self.daily_rate


@dataclass(frozen=True)
class DailySettlement(EntityRecord):
    settlement_id:int|None
    settlement_date:str
    total_sales:int
    material_cost:int
    labor_cost:int
    net_profit_loss:int
    previous_loss:int
    accumulated_loss:int
    distributable_profit:int
    partner_shares:str
    expected_cash:int
    actual_cash:int
    cash_difference:int
    difference_note:str
    closed_by:int
    closed_at:str

    @staticmethod
    def compute(total:int,material:int,labor:int,previous_loss:int)->SettlementAmounts:
        net=total-material-labor
        distributable=max(0,net-previous_loss)
        next_loss=max(0,previous_loss-net)
        shares=tuple(distributable//4+(1 if i<distributable%4 else 0) for i in range(4))
        return SettlementAmounts(net,next_loss,distributable,shares)


@dataclass(frozen=True)
class DailyWage(EntityRecord):
    wage_id:int|None
    settlement_id:int
    staff_id:int
    name_snapshot:str
    wage_amount:int
    recorded_at:str

    @classmethod
    def for_staff(cls,staff:Staff,settlement_id:int,stamp:str):
        return cls(wage_id=None,settlement_id=settlement_id,staff_id=staff.staff_id,name_snapshot=staff.name,wage_amount=staff.payable_wage(),recorded_at=stamp)

    def insert_values(self)->tuple:
        return (self.settlement_id,self.staff_id,self.name_snapshot,self.wage_amount,self.recorded_at)


@dataclass(frozen=True)
class OrderBatch(EntityRecord):
    batch_id:int|None
    order_id:int
    status:str
    created_at:str
    updated_at:str
    updated_by:int|None
    kitchen_job_id:int|None
    legacy:int

    def next_status(self)->str|None:
        return {'RECEIVED':'PREPARING','PREPARING':'READY','READY':'SERVED'}.get(self.status)
