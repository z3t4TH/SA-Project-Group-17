"""Regenerate public image attribution from the reviewed local manifest."""
import json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'assets/menu';items=json.loads((p/'image-credits.json').read_text())
intro='ภาพประกอบสำหรับสาธิต ไม่ใช่ภาพอาหารจริงของร้าน แต่ละรายการใช้คนละภาพ รวมตัวเลือกต่างขนาด บางภาพเป็นอาหารใกล้เคียง วัตถุดิบ สูตร ปริมาณ บรรจุภัณฑ์ และการจัดจานอาจต่างจากเมนูจริง ไม่มีการรับรองร้านจากผู้สร้างภาพ'
lines=['# เครดิตภาพประกอบเมนู','',intro,'','แต่ละภาพคงสิทธิ์ตาม license ของตน การรวมภาพไว้ใน repository ไม่ได้เปลี่ยน license ของภาพ ส่วน placeholder.svg สร้างสำหรับโครงการนี้','','| รายการ / ไฟล์ | ผู้สร้าง | สิทธิ์ | ต้นทาง |','|---|---|---|---|']
body='<h1>เครดิตภาพประกอบเมนู</h1><p>'+html.escape(intro)+'</p>'
for x in items:
    lic=x['license_url'];name=x['menu_name'];author=x['author']
    lines.append(f'| {name} / {x["key"]}.jpg | {author.replace("|", "/")} | [{x["license"]}]({lic}) | [{x["title"].replace("|", "/")}]({x["source"]}) |')
    body+=f'<article><h2>{html.escape(name)}</h2><img src="{html.escape(x["file"])}" width="200" loading="lazy" alt="ภาพประกอบ {html.escape(name)}"><p>{html.escape(author)} · <a href="{html.escape(lic)}">{html.escape(x["license"])}</a> · <a href="{html.escape(x["source"])}">{html.escape(x["title"])}</a></p><p>{html.escape(x["changes"])} Retrieved {html.escape(x["retrieved"])}.</p></article>'
lines+=['','ดาวน์โหลด 5 พฤศจิกายน 2026 ใช้ thumbnail จาก Wikimedia Commons ขนาดกว้าง 640px เมื่อมีให้ ไฟล์ต้นฉบับที่เล็กกว่าใช้ขนาดเดิม แสดงด้วย CSS object-fit:cover โดยไม่แก้ไขเนื้อหาไฟล์ภาพ ภาพ CC BY-SA และการดัดแปลงภาพต้องรักษาเงื่อนไข ShareAlike ของภาพนั้น ดู URL license, ชื่อไฟล์ต้นทาง, menu_key และ sha256 ใน image-credits.json','']
(p/'IMAGE_CREDITS.md').write_text('\n'.join(lines))
(p/'image-credits.html').write_text('<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>เครดิตภาพเมนู</title><style>body{max-width:850px;margin:30px auto;padding:20px;font:16px system-ui;line-height:1.7}article{border-bottom:1px solid #ddd;padding:20px 0}img{height:130px;object-fit:cover}</style>'+body+'</html>')
