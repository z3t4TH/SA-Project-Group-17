"""Shared validation, money and SQLite row helpers for domain classes."""
import hashlib
import re
import secrets
from decimal import Decimal,InvalidOperation
from datetime import date
from config import ROOT,TZ

class Problem(Exception):
    def __init__(self, message, status=400, **details):
        self.message, self.status, self.details = message, status, details


def require(condition, message, status=400, **details):
    if not condition:
        raise Problem(message, status, **details)


def money(value):
    try:
        d = Decimal(str(value))
        require(d.is_finite() and 0 <= d <= 10000000 and d == d.quantize(Decimal('.01')),
                'จำนวนเงินต้องอยู่ระหว่าง 0 ถึง 10,000,000 บาท และทศนิยมไม่เกิน 2 ตำแหน่ง')
        return int(d * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise Problem('กรุณาระบุจำนวนเงินให้ถูกต้อง')


def integer(value, low=1, high=20):
    text=str(value)
    require(not isinstance(value,bool) and re.fullmatch(r'[0-9]+',text) is not None, 'กรุณาระบุจำนวนเต็ม')
    digits=text.lstrip('0') or '0'
    require(len(digits)<=len(str(high)), f'จำนวนต้องอยู่ระหว่าง {low} ถึง {high}')
    v = int(digits)
    require(low <= v <= high, f'จำนวนต้องอยู่ระหว่าง {low} ถึง {high}')
    return v


def calendar_date(value):
    require(isinstance(value,str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value) is not None,'วันที่ไม่ถูกต้อง')
    try:date.fromisoformat(value)
    except ValueError:raise Problem('วันที่ไม่ถูกต้อง')
    return value


def string(value, maximum=100):
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum, f'กรุณากรอกข้อความ 1–{maximum} ตัวอักษร')
    return value.strip()


def phone(value, optional=False):
    if optional and not value:
        return ''
    require(isinstance(value, str) and re.fullmatch(r'0[0-9]{8,9}', value), 'เบอร์โทรศัพท์ต้องขึ้นต้นด้วย 0 และมี 9–10 หลัก')
    return value


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 200000).hex()
    return salt + ':' + digest


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args)]


def one(c, sql, args=(), message='ไม่พบรายการ'):
    r = c.execute(sql, args).fetchone()
    require(r is not None, message, 404)
    return dict(r)


def rows_as_pairs(c,sql):
    return [(r[0],r[1]) for r in c.execute(sql)]
