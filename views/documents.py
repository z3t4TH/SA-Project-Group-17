"""HTML Views. Rendering consumes Model data and never queries SQLite."""
import html
import json

from config import ROOT
from restaurant_profile import PROFILE
import qr
from models.entities import OrderItem


def esc(v): return html.escape(str(v))

def baht(v): return f'{v/100:,.2f} บาท'


class RestaurantView:
    """Server Boundary: templates and printable HTML, with no database access."""

    @staticmethod
    def index_document():
        return (ROOT/'views/templates/index.html').read_bytes()

    @staticmethod
    def print_document(title, body, demo=False):
        return f'''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
        <style>body{{font:16px Tahoma,sans-serif;line-height:1.8;color:#182d29;max-width:850px;margin:32px auto;padding:24px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ccc}}tr{{break-inside:avoid}}h1,h2,h3{{break-after:avoid}}svg{{width:250px}}.notice{{padding:10px;background:#fff2d0}}button{{background:#205b46;color:white;border:0;border-radius:8px;padding:12px 18px;font:inherit;cursor:pointer}}@media print{{body{{margin:0;padding:0}}.no-print{{display:none}}}}@page{{size:A4;margin:18mm}}</style><script defer src="/static/print.js"></script>
        <div class="no-print"><button id="print-document">พิมพ์ / บันทึกเป็น PDF</button></div><h2>{esc(PROFILE['name'])}</h2><p>{esc(PROFILE['location'])} • โทร. {esc(PROFILE['phone'])}</p><h1>{esc(title)}</h1>{'<p class="notice">ข้อมูลสาธิตสมมติ • ไม่ใช่หลักฐานการเงินของร้านจริง</p>' if demo else ''}{body}<hr><p class="no-print">เลือก Save as PDF / บันทึกเป็น PDF ในหน้าต่างพิมพ์ของเบราว์เซอร์</p></html>'''

    @staticmethod
    def render_print_job(data,base_url,demo=False):
        j=data['job'];d=data['payload'];bill=data['bill'];jid=j['job_id']
        title={'QUEUE':'บัตรคิว','SESSION':'QR สั่งอาหารประจำโต๊ะ','KITCHEN':'ใบรายการครัว','RECEIPT':'ใบเสร็จรับเงิน'}[j['kind']]
        body=f'<p>เอกสาร #{jid} • {esc(j["created_at"])}</p>'
        if j['kind']=='QUEUE':body+=f'<h2>Q{d["number"]:03}</h2><p>{d["guests"]} ท่าน • {esc(d["date"])}</p>'
        if j['kind']=='SESSION':
            link=base_url+'/order/'+d['token'];body+=f'<h2>โต๊ะ {esc(d["table_number"])}</h2>{qr.svg(link)}<p><a href="{esc(link)}">เปิดหน้าสั่งอาหาร</a></p><p>QR ใช้ได้เฉพาะรอบนี้ และหมดอายุเมื่อปิดโต๊ะ</p>'
        if j['kind']=='KITCHEN':
            body+=f'<h2>โต๊ะ {esc(d["table_number"])}</h2><table><tr><th>รายการ</th><th>จำนวน</th><th>หมายเหตุ</th></tr>'
            body+=''.join(f'<tr><td>{esc(i["name"])}</td><td>{i["quantity"]}</td><td>{esc(i["note"])}</td></tr>' for i in d['items'])+'</table>'
        if j['kind']=='RECEIPT':
            pay=bill['payment'][0]
            body+=f'<p>บิล #{d["order_id"]} • โต๊ะ {esc(bill["order"]["table_number"])}</p><table><tr><th>รายการ</th><th>จำนวน</th><th>รวม</th></tr>'
            body+=''.join(f'<tr><td>{esc(i["name_snapshot"])}</td><td>{i["quantity"]}</td><td>{baht(OrderItem.from_row(i).line_total())}</td></tr>' for i in bill['items'])+'</table>'
            body+=f'<h2>ยอดสุทธิ {baht(pay["total_paid"])}</h2><p>{"เงินสด" if pay["payment_method"]=="CASH" else "Mock QR • การชำระจำลอง"} • รับ {baht(pay["amount_received"])} • ทอน {baht(pay["change_amount"])}</p><p>เอกสารต้นแบบ ไม่ใช่ใบกำกับภาษี</p>'
        return print_document(title,body,demo)

    @staticmethod
    def render_report(data,demo=False):
        date=data['date'];sales=data['sales'];s=data['settlement']
        body=f'<p>วันที่ {esc(date)}</p><h2>รายงานยอดขาย</h2><p>ยอดรวม {baht(sales["total"])} • {sales["count"]} บิล • เงินสด {baht(sales["cash"])} • Mock QR {baht(sales["qr"])}</p><table><tr><th>ใบรับเงิน</th><th>โต๊ะ</th><th>วิธีชำระ</th><th>ยอดสุทธิ</th></tr>'
        body+=''.join(f'<tr><td>#{p["payment_id"]}</td><td>{esc(p["table_number"])}</td><td>{"เงินสด" if p["payment_method"]=="CASH" else "Mock QR (จำลอง)"}</td><td>{baht(p["total_paid"])}</td></tr>' for p in sales['payments'])+'</table>'
        if s:
            body+='<h2>รายงานผลประกอบการและจัดสรรเงิน</h2><table>'
            for label,key in [('รายรับ','total_sales'),('ต้นทุนวัตถุดิบ/ค่าใช้จ่าย','material_cost'),('ค่าแรง','labor_cost'),('กำไร/ขาดทุนวันนี้','net_profit_loss'),('ขาดทุนยกมา','previous_loss'),('ขาดทุนยกไป','accumulated_loss'),('กำไรจัดสรร','distributable_profit'),('เงินสดตามระบบ','expected_cash'),('เงินสดจริง','actual_cash'),('ส่วนต่างเงินสด','cash_difference')]:body+=f'<tr><td>{label}</td><td>{baht(s[key])}</td></tr>'
            body+='</table><p>เหตุผลส่วนต่าง: '+esc(s['difference_note'])+'</p><h3>ส่วนแบ่งหุ้นส่วน 4 ส่วน</h3>'
            body+=''.join(f'<p>ส่วนที่ {i+1}: {baht(v)}</p>' for i,v in enumerate(json.loads(s['partner_shares'])))
            body+='<h3>ค่าแรงรายบุคคลที่บันทึก</h3><table><tr><th>ชื่อ</th><th>ค่าแรง</th></tr>'
            body+=''.join(f'<tr><td>{esc(w["name_snapshot"])}</td><td>{baht(w["wage_amount"])}</td></tr>' for w in data['wages'])+'</table>'
            body+=f'<p>ผู้ปิดบัญชี #{s["closed_by"]} • {esc(s["closed_at"])}</p>'
        else:body+='<p>ยังไม่ได้ปิดบัญชีวันนี้ รายงานผลประกอบการยังไม่สมบูรณ์</p>'
        return print_document('รายงานยอดขายและผลประกอบการ',body,demo)


index_document=RestaurantView.index_document
print_document=RestaurantView.print_document
render_print_job=RestaurantView.render_print_job
render_report=RestaurantView.render_report
