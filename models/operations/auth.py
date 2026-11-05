"""AuthOperations: persistent business operations inside an existing transaction."""
import hmac
import json
import secrets
from datetime import datetime,timedelta
from models.common import Problem,require,money,integer,string,phone,password_hash,rows,one
from models.operations.base import DomainOperations


class AuthOperations(DomainOperations):
    def login(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        r=c.execute('SELECT * FROM Users WHERE username=?',(str(b.get('username','')),)).fetchone()
        dummy='0'*32+':'+'0'*64
        expected=r['password_hash'] if r else dummy
        require(hmac.compare_digest(password_hash(str(b.get('password','')),expected.split(':')[0]),expected),'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง',401)
        token=secrets.token_urlsafe(32)
        c.execute('INSERT INTO Sessions VALUES(?,?,?)',(token,r['user_id'],(restaurant.now()+timedelta(hours=12)).isoformat(timespec='seconds')))
        return {'token':token}

    def logout(self,c,b,u):
        restaurant=self.restaurant;now=restaurant.stamp()
        c.execute('DELETE FROM Sessions WHERE user_id=?',(u['user_id'],))
        return {'message':'ออกจากระบบแล้ว'}
