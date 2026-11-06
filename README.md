# ร้านส้มตำ เมี่ยงคำ — ระบบร้านอาหาร MVC

ระบบต้นแบบภาษาไทยสำหรับจองโต๊ะ จัดคิว สั่งอาหารผ่าน QR ติดตามสถานะครัว รับชำระเงิน และปิดบัญชี ใช้ **Python 3.10+ standard library + SQLite + HTML/CSS/JavaScript** ไม่ต้องติดตั้ง npm หรือ Python packages เพื่อรันโปรแกรม รองรับ macOS/Linux (ตัวล็อกฐานข้อมูลใช้ fcntl)

## เปิด Presentation Demo

เปิด Terminal ในโฟลเดอร์ที่แตกไฟล์โครงการ แล้วรัน:

```sh
python3 manage.py seed-presentation
python3 app.py --mode presentation --port 8002
```

เปิด [หน้าร้าน](http://127.0.0.1:8002/app) หรือ [จองโต๊ะ](http://127.0.0.1:8002/book) หยุดด้วย Ctrl+C บน macOS ใช้ `start-presentation.command` ได้

| บัญชีสาธิต | Username | Password |
|---|---|---|
| เจ้าของร้าน | owner | owner1234 |
| พนักงาน | staff | staff1234 |

ข้อมูลถูกสร้างใน `data/presentation.sqlite3` แยกจากฐานเดิม โหมดนี้ใช้ **วันจำลอง 5 พฤศจิกายน 2026 เวลา 13:30 น.** คงที่ มีประวัติวันที่ 3–4 พฤศจิกายนที่ปิดบัญชีแล้ว และวันที่ 5 ที่ยังเปิดบริการ จึงใช้สาธิตได้แม้วันจริงเปลี่ยนไป ดูลำดับนำเสนอ 5–10 นาทีใน [DEMO.md](DEMO.md)

```sh
python3 manage.py verify-presentation
# หยุดเซิร์ฟเวอร์ก่อนรีเซ็ต; สำรองฐาน Presentation เดิมโดยอัตโนมัติ
python3 manage.py reset-presentation
# เปลี่ยนวันจำลอง โดยเลือกวันอังคาร–อาทิตย์
python3 manage.py reset-presentation --date 2026-11-06
```

คำสั่งสร้างซ้ำไม่เพิ่มรายการซ้ำ และไม่เขียนทับการทดลองที่ทำไว้ การรีเซ็ตทำได้เฉพาะฐานชื่อ presentation.sqlite3 ที่มีเครื่องหมาย Presentation และ mode=demo เท่านั้น ไม่ใช้คำสั่งนี้กับ demo/live ของร้าน

## โหมดอื่น

| โหมด | คำสั่ง | ฐานข้อมูล / เวลา |
|---|---|---|
| สาธิตเริ่มต้น มีเมนูแต่ไม่เติมธุรกรรม | `python3 app.py --mode demo` | data/demo.sqlite3 / เวลาจริง |
| ข้อมูลจริง ครั้งแรก | `python3 app.py --mode live --init-owner` | data/live.sqlite3 / ตั้งรหัสผ่านเจ้าของเอง |
| ข้อมูลจริง ครั้งถัดไป | `python3 app.py --mode live` | data/live.sqlite3 / เวลาจริง |

โหมด live ไม่มีโต๊ะ พนักงาน หรือรหัสผ่านสาธิต ให้เพิ่มผ่านตั้งค่าร้าน บัญชีเข้าใช้แยกจากรายชื่อคิดค่าแรง และห้ามเปิดฐานเดียวกันจากเซิร์ฟเวอร์หลายตัวพร้อมกัน

```sh
python3 manage.py backup --mode demo
python3 manage.py backup --mode live
python3 manage.py backup --mode presentation
```

ไฟล์สำรองอยู่ data/backups ไม่เขียนทับสำเนาเดิม `reset-demo` ใช้เฉพาะ demo เดิมและเก็บสำเนาก่อน ไม่ใช่คำสั่งสร้าง Presentation

## เมนูและภาพประกอบ

เมนูจากภาพเจ้าของร้านมี 157 รายการ/ตัวเลือก เปิดให้สั่ง 154 อีก 3 รายการรอยืนยันราคา ได้แก่ ปลาดุกย่าง ซุปหน่อไม้ และไส้กรอก/ไส้อั่ว โปรแกรมยังป้องกันการสั่งรายการเหล่านี้และไม่เปลี่ยนราคา snapshot ของบิลเก่า

ภาพประกอบ 157 ภาพเก็บใน `assets/menu/images` แยกต่อรายการและตัวเลือกต่างขนาด ไม่ใช้ไฟล์หรือแหล่งภาพเดิมซ้ำ บางภาพเป็นอาหารใกล้เคียง สูตร วัตถุดิบ ขนาด และบรรจุภัณฑ์อาจต่างจากจริง พร้อมภาพสำรองเมื่อโหลดไม่ได้ เป็น **ภาพประกอบจากบุคคลอื่น ไม่ใช่ภาพอาหารจริงของร้าน** ดู [เครดิตและสิทธิ์ภาพ](assets/menu/IMAGE_CREDITS.md) หรือ `/image-credits` ภาพแต่ละไฟล์คงสิทธิ์ของเจ้าของตาม CC BY / CC BY-SA / Public domain การรวมไว้ในโครงการไม่เปลี่ยน license ของภาพ

## โครงสร้าง

ดูข้อมูลแบบข้อความบน GitHub ได้ที่ [examples/readable-data](examples/readable-data/README.md): SQL พร้อมโครงสร้างและข้อมูลสาธิตสามวัน รวม CSV แยก 20 ตาราง เป็น snapshot ที่ล้างข้อมูลเข้าสู่ระบบแล้ว ไม่ใช่ฐานข้อมูลสดของร้าน

```text
app.py / manage.py          เปิดระบบ / สำรอง / จัดข้อมูลสาธิต
models/                    Entity, ธุรกรรม, Operations, ข้อมูลสาธิต และภาพเมนู
controllers/               HTTP Controller และ Use-case Managers
views/                     HTML เอกสารและ template
static/                    Boundary classes, เหตุการณ์ และ CSS
assets/menu/               catalog และภาพประกอบที่แจกจ่ายได้ พร้อมเครดิต
migrations/                SQLite schema version 1–3 รวม 20 ตาราง
tests/                    ชุดทดสอบ ใช้ฐานชั่วคราว
tools/                    สร้างเครดิตภาพ / SQL catalog / ชุดส่งมอบ
docs/                     คู่มือและผลตรวจชุดส่งมอบ
```

ดู [MVC](docs/MVC.md), [ฐานข้อมูลและกฎธุรกิจ](docs/ARCHITECTURE.md), [สถานะครัว](docs/ORDER_STATUS.md), [ผลตรวจ](docs/RELEASE_CHECKS.md) และ [รายการจัดเก็บไฟล์เก่า](docs/CLEANUP.md)

## ทดสอบและจัดชุด GitHub

```sh
python3 -m unittest discover -s tests -v
python3 tools/build_release.py
```

คำสั่งจัดชุดสร้าง `dist/sa-restaurant-github/` และ ZIP จากรายการไฟล์ที่อนุญาต ไม่คัดลอกฐานข้อมูล sessions/token รหัสลิงก์ tunnel logs archive หรือไฟล์ทดลอง ผู้ดาวน์โหลดสร้าง Demo จาก seed ได้เอง ไม่ต้องมีไฟล์ส่วนตัวในเครื่องต้นทาง

`.gitignore` กัน data/, .local-archive/, .tools/, dist/, caches, .env และกุญแจส่วนตัวออกจาก Git repository ใช้เฉพาะโค้ดและ assets ที่ตรวจแล้ว ฐานข้อมูลและบัญชีที่เพิ่มเฉพาะเครื่องไม่ถูกนำขึ้น GitHub ไม่กำหนดสิทธิ์เผยแพร่โค้ดแทนเจ้าของ; สิทธิ์ภาพประกอบระบุแยกรายไฟล์

## QR และขอบเขตต้นแบบ

QR ใช้ origin ที่กำลังรันและ token ของบิล ไม่มี URL ชั่วคราวฝังใน seed ถ้าใช้ localhost มือถือเครื่องอื่นจะเข้าลิงก์นั้นไม่ได้ สำหรับ LAN ใช้ IP เครื่องเดียวกันกับ `--base-url` และ `--host` บนเครือข่ายที่ไว้ใจ ส่วน HTTPS tunnel เป็นตัวเลือกแยกใน [REMOTE_PREVIEW.md](docs/REMOTE_PREVIEW.md) และต้องติดตั้ง cloudflared เพิ่ม ไม่รวม binary ใน GitHub ZIP

ระบบรองรับเงินสดและ **Mock QR ที่ไม่เชื่อมธนาคาร** งานพิมพ์เปิดเอกสารให้เบราว์เซอร์พิมพ์ ไม่ตรวจเครื่องพิมพ์จริง ไม่มีภาษี คืนเงิน สต็อกวัตถุดิบ หรือแก้ประวัติบัญชีที่ปิดแล้ว การรับเงินแยกจากสถานะเสิร์ฟ สามารถมีงานครัวค้างหลังรับเงิน และหน้าครัวยังแสดงงานนั้น

เปิดลิงก์ Cloudflare ทดสอบด้วย `python3 preview.py` หลังติดตั้ง cloudflared หน้าลูกค้าเข้าได้ทันทีโดยไม่มีรหัสเปิดลิงก์ หน้าร้านยังต้องล็อกอิน ตัวเปิดนี้ใช้ฐาน Demo เดิม ส่วน Presentation พอร์ต 8002 แยกกัน ดู [คู่มือลิงก์ภายนอก](docs/REMOTE_PREVIEW.md)

ฐานข้อมูลเป็น SQLite Relational Database มี 20 ตาราง พร้อม Primary/Foreign Keys ดู [ตารางและตัวอย่าง SQL](docs/DATABASE.md) และ migrations/ สำหรับโครงสร้างแบบข้อความ

ผลทดสอบล่าสุด 103 test methods รวม edge cases / concurrency / HTTP / accounting ดู [QA report](docs/QA_REPORT.md) และ [รายการ tests](docs/QA_TEST_CASES.md)

## GitHub

Repository: [z3t4TH/SA-Project-Group-17](https://github.com/z3t4TH/SA-Project-Group-17) แบบ Private ผู้ดาวน์โหลดต้องมีสิทธิ์เข้าถึง

```sh
git clone https://github.com/z3t4TH/SA-Project-Group-17.git
cd SA-Project-Group-17
python3 app.py --mode demo
```

บัญชีสาธิตที่สร้างจาก seed คือ owner / owner1234 และ staff / staff1234 บัญชีพนักงานเพิ่มเติมในเครื่องเจ้าของไม่ถูกรวมใน Git ให้เจ้าของสร้างบัญชีใหม่จาก ตั้งค่าร้าน → สร้างบัญชีเข้าสู่ระบบ และเลือกสิทธิ์ STAFF รายชื่อพนักงานคิดค่าแรงกับบัญชีเข้าสู่ระบบเป็นคนละตาราง
