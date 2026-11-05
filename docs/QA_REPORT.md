# รายงานทดสอบระบบร้านอาหาร

วันที่: 5 พฤศจิกายน 2026 • ผู้ทดสอบ: Software testing agent

## ผลสรุป

ชุดเดิม 73 tests ผ่านก่อนเริ่ม เพิ่ม 30 regression / edge tests รวม **103 tests ผ่านทั้งหมด** รอบ source ล่าสุดใช้เวลา 18.257 วินาที ไม่มี skip ทดสอบด้วย Python 3.14 บน macOS ชุดเดียวกันมีหลาย subcases รวม property checks เงิน 250 ค่าและการจัดสรร 500 ชุด ตัวเลข 103 หมายถึง test methods ไม่ใช่จำนวน input combinations หรือเปอร์เซ็นต์ code coverage

ใช้ฐานข้อมูลชั่วคราวในแต่ละ test และฐาน QA สำหรับเบราว์เซอร์ที่พอร์ต 8004 แยกจาก demo.sqlite3 / presentation.sqlite3 ของผู้ใช้ ไม่ reset ฐานเดิม ตรวจฐาน Demo เดิม, Presentation เดิม และ QA: integrity_check=ok และ foreign_key_check=0 ทุกฐาน

## ปัญหาที่พบและแก้

| รหัส | ระดับ | หลักฐานก่อนแก้ | การแก้และผลทดสอบซ้ำ |
|---|---|---|---|
| QA-001 | Medium | GET จำนวนคนเป็น ², ① หรือเลข 5,000 หลัก ตอบ HTTP 500; validator หลุดเป็น ValueError | รับเฉพาะเลขฐานสิบ 0–9 และตรวจความยาวก่อน int; คืน 400 / Problem โดยไม่เขียนข้อมูล |
| QA-002 | Medium | รายงานยอมรับ 2026-02-30, 2026-13-01, ปี 0000; report_data ไม่ตรวจรูปแบบครบ | ตรวจ ISO date และวันที่ปฏิทินจริงทั้ง snapshot และ report_data; ปฏิเสธด้วย 400 |
| QA-003 | Medium | QR 107 ASCII bytes หรือภาษาไทย 108 UTF-8 bytes ตอบ 500 | ตรวจขนาดไม่เกิน 106 UTF-8 bytes ก่อนสร้าง SVG; เกินขนาดคืน 400; 106 bytes และภาษาไทย 105 bytes ผ่าน |
| QA-004 | Medium | โหลดอ่าน 120 คำขอพร้อมกัน 8 workers พบ connection reset 1–3 คำขอในรอบที่ตรวจ; backlog ของ HTTP server เดิม=5 | เพิ่ม RestaurantHTTPServer request_queue_size=64 ใน app.py และ preview.py; เพิ่ม regression test burst 120 reads; หลังแก้สามรอบรวม 360/360 ไม่มี error |

เสริมการรับ JSON: ปฏิเสธ nesting เกิน 64 ระดับ และจับ RecursionError จาก decoder เป็น 400 ก่อน hashing/dispatch เพิ่มการทดสอบ malformed UTF-8/JSON, array/scalar/null และ JSON ลึกมาก ข้อความตอบกลับไม่เปิด traceback

ไม่เปลี่ยน schema / ราคาหรือชื่อเมนู / ชื่อคลาสธุรกิจ เพิ่มเพียงคลาสโครงสร้างพื้นฐาน RestaurantHTTPServer และฟังก์ชัน calendar_date

## ขอบเขตอัตโนมัติ

| กลุ่ม | สิ่งที่ตรวจจริง |
|---|---|
| การจอง | ชื่อว่าง/ยาว/ผิดชนิด, เบอร์ 9–10 หลักและเบอร์ผิด, จำนวน 0/1/20/เกินโต๊ะ/เกินเพดาน, รอบอดีต/อนาคตเกินช่วง/นาทีไม่ตรง, ก่อนและตรงเวลาเริ่ม, วันจันทร์, วันเปลี่ยน, เต็มโควตา, cancel คืนโควตา, check-in ผิดวัน/โต๊ะเล็ก/โต๊ะซ้ำ, No-Show ตรง 15 นาทีและเกิน 1 วินาที |
| คิวและโต๊ะ | FIFO, ต้องเรียกก่อนจัดโต๊ะ, เรียกได้ 3 ครั้ง, skip ก่อนครบไม่ได้, cancel/ประวัติพิมพ์, เลขคิวพร้อมกัน 24 งานไม่ซ้ำ, เปิดโต๊ะพร้อมกันมีผู้ชนะเดียว, จัดสองคิวลงโต๊ะเดียวมีผู้ชนะเดียว, ห้ามแก้โต๊ะ HELD/OCCUPIED |
| เมนูและออร์เดอร์ | รายการรอยืนยันราคา, หมด, ราคาเปลี่ยน, snapshot ราคา/ชื่อเดิม, ตะกร้า 0/50/51 บรรทัด, จำนวน 0/1/99/100, note 255/256, ผิดชนิด, รายการไม่พบ, atomic rollback ทั้ง items/batches/print jobs, หลายรอบในวินาทีเดียว |
| ครัว | RECEIVED→PREPARING→READY→SERVED, ย้อน/ข้ามขั้น/แก้ terminal ไม่ได้, optimistic conflict สองพนักงาน, history, ลูกค้าเห็นเฉพาะโต๊ะตน, ออร์เดอร์ที่ยังไม่เสิร์ฟไม่หายเมื่อรับชำระหรือเปลี่ยนวัน |
| การเงิน | เงินสดไม่พอ/พอดี/เงินทอน, ทศนิยม 2 ตำแหน่ง, 1 สตางค์, NaN/Infinity/ติดลบ/เกิน 10 ล้านบาท, Mock QR ต้องยืนยัน, stale total, รับเงินซ้ำ, บิลยอดศูนย์/ของแถม, ปิดแล้ว QR ใช้ไม่ได้, ยอดขายนับสุทธิไม่ใช่เงินรับรวมเงินทอน |
| บัญชี | ค่าแรง snapshot, พนักงาน inactive/ซ้ำรวม ID ต่างรูป 2 กับ 02, ขาดทุนยกมา, เศษสตางค์ 4 ส่วนรวมตรง, actual cash ไม่ตรงต้องมีเหตุผล, ปิดซ้ำ/โต๊ะหรือคิวค้าง/การจองค้างไม่ได้, วันที่ย้อนหลัง, รายงาน historical, random lifecycle 24 บิล |
| การชนกัน/กู้คืน | retry พร้อมกัน 24 งานจองได้รายการเดียว, retry อาหารพร้อมกันมี batch เดียว, เปลี่ยน body ด้วย key เดิมถูกปฏิเสธ, failed request retry ได้, แข่งสั่งเพิ่มกับจ่ายเงินยอดยังตรง, concurrent payment มีรายการเดียว, จำลอง print/insert failure แล้ว rollback |
| สิทธิ์และ HTTP | ทุก write route ที่ต้องล็อกอิน, owner-only routes ปฏิเสธ staff, session หมดอายุตรง 12 ชม., logout, Host/Origin/CSRF, missing idempotency key, body 100,001 bytes, invalid Content-Length/Content-Type, login rate limit, cookie Secure/HttpOnly/SameSite, traversal/private files, SQL injection เป็นข้อมูล, HTML escaping |
| ฐานข้อมูล/ติดตั้ง | 20 ตารางและ FK, integrity/FK checks, immutable financial records, backup ไม่ทับ, process lock, migrations v1/v2→v3, live ไม่มี seed/บัญชีสาธิต, ห้ามปนโหมด, Presentation reset guard/seed ซ้ำ, 157 ภาพ local คนละ source/hash |

สำเนาสะอาดจาก GitHub allowlist ผ่าน 103/103 เช่นกันใน 17.298 วินาที และสร้าง/verify Presentation สามวันจาก seed ได้โดยไม่มีไฟล์ data เดิม ส่วนการ smoke ระบบที่เปิดใหม่ทั้ง localhost และ Cloudflare ตรวจ /book=200, /api/state ที่ไม่ล็อกอิน=401, ตัวเลขพิเศษและ QR เกินขนาด=400

รายชื่อครบทุก test method อยู่ใน [QA_TEST_CASES.md](QA_TEST_CASES.md)

## ทดสอบผ่านเบราว์เซอร์จริง

ใช้ข้อมูลบุคคลสมมุติและฐาน QA แยก:

1. ฟอร์มจองปฏิเสธชื่อว่างและเบอร์ 123; ไม่เลือกรอบแล้วแจ้งเตือน รอบที่ผ่านแล้วกดไม่ได้
2. จอง 14:00 พร้อมชื่อที่มี `<script>` แล้วแสดงเป็นข้อความ ไม่เกิด script element ใน modal; รหัสจองปรากฏในหน้าร้าน
3. ค้นหารหัส → check-in → โต๊ะ T05 เปลี่ยน HELD → เปิด QR → ลิงก์ใช้ origin พอร์ต 8004 ของรอบนั้น
4. จำนวนอาหาร 0 ถูกปฏิเสธ; ส่งเมี่ยงคำเล็ก 2 ชุด 100 บาท และใหญ่ 1 ชุด 80 บาท เป็นสอง batches; note `<img onerror>` แสดงเป็นข้อความ ไม่มี img ถูกแทรกใน cart
5. พนักงานเลื่อนทั้งสอง batches ครบทุกขั้น ลูกค้ากดอัปเดตแล้วเห็น SERVED ทั้งคู่
6. เงินรับ 100 บาทถูกปฏิเสธเมื่อบิล 180 บาท; รับ 200 ทอน 20, ใบเสร็จแสดงยอดถูก, โต๊ะคืน AVAILABLE, โหลด QR เดิมแล้วหมดอายุ ตรวจ SQLite ยืนยัน order=18,000, received=20,000, change=2,000 สตางค์ และ 2 batches เป็น SERVED
7. ค้นหาจองด้วยเบอร์ผิดไม่พบ; รายการ CHECKED_IN ไม่แสดงปุ่มยกเลิก; รายการ CONFIRMED ที่ยังไม่ถึงเวลายกเลิกและคืนโควตาได้
8. รายงาน 4 พ.ย.: ขาย 2,840 ต้นทุน 300 ค่าแรง 1,250 กำไร 1,290 ชดเชยขาดทุน 500 เหลือ 790 แบ่ง 197.50 บาท ×4
9. ล็อกอินผิดถูกปฏิเสธ; owner เข้าได้; logout แล้ว staff เข้าได้และไม่เห็นเมนูรายงานเจ้าของ/ตั้งค่าร้าน
10. ตรวจ geometry หน้าจอง และหน้ารายการจอง/คิว/ครัว/เมนู/รายงาน/ตั้งค่า ที่ 320, 390, 768, 1280 px รวม 28 จุด: scrollWidth เท่ากับ viewport ทุกจุด คืน viewport หลังตรวจ (เป็น responsive emulation ไม่ใช่โทรศัพท์จริง)

## QR และการอ่านพร้อมกัน

นำ matrix ที่โปรแกรมสร้างมาทำ PNG แล้วถอดรหัสด้วย macOS CoreImage ซึ่งเป็น decoder อิสระ 4 กรณี: URL 60 bytes, ASCII 106 bytes, ภาษาไทย 105 bytes, ข้อความที่ต้อง escape ใน SVG ทั้ง 4 อ่านกลับได้ตรงต้นฉบับ การรันครั้งแรกภายใต้สิทธิ์จำกัดใช้ CoreImage ไม่ได้; เมื่อรันด้วยสิทธิ์ที่จำเป็นจึงผ่าน ไม่ได้นับรอบที่ถอดรหัสไม่ได้เป็นผลผ่าน

อ่านแบบ loopback 8 workers หลังแก้รวม 360 requests ผ่านทุกคำขอ รอบที่บันทึกเพิ่มเติม median 3.58–4.235 ms / p95 15.31–23.08 ms ตัวเลขนี้เป็นเครื่องทดสอบ ไม่ใช่ SLA ความเร็วอินเทอร์เน็ตหรือขีดจำกัด production

## หลักฐานและการทำซ้ำ

```sh
python3 -m unittest discover -s tests -v
python3 manage.py seed-presentation
python3 manage.py verify-presentation
```

บันทึกเฉพาะเครื่องใน data/: qa-baseline-tests.log, qa-edge-red.log, qa-edge-second-red.log, qa-full-final-tests.log, qa-database-verification.json, qa-load-before-fix.json, qa-load-repeat-results.json, qa-qr-results.json, qa-responsive-results.json และ release-evidence/qa-*.png ไม่รวม logs หรือฐานที่มี session/token ใน ZIP

ก่อนเปิด preview ใหม่ สำรอง Demo ผ่าน SQLite backup API แล้วเทียบแถวข้อมูล 19 ตาราง (ยกเว้น Sessions) ก่อน/หลังเปิดใหม่ตรงกันทั้งหมด ฐานข้อมูลเดิมไม่ถูก reset

## ข้อจำกัดและพฤติกรรมที่ควรทราบ

ไม่สามารถยืนยันว่าโปรแกรมไร้บั๊กหรือทดสอบทุกชุดผสมที่เป็นไปได้ การผ่าน 103 tests ไม่ใช่ coverage 100% ไม่มีเครื่องมือวัด branch coverage ในรอบนี้

ยังไม่ได้ทดสอบกับธนาคาร/การชำระเงินจริง เครื่องพิมพ์จริง โทรศัพท์จริง ทุก browser/OS ระบบหลายเครื่องที่ใช้ไฟล์ DB ร่วมกัน หรือไฟดับ/ดิสก์เสียจริง การ rollback ใช้การจำลองข้อผิดพลาดและ race เฉพาะเครื่อง ส่วน load ใช้ 8 workers ไม่ใช่การทดสอบ capacity สูงสุด/ระยะยาวหรือ penetration test เต็มรูปแบบ

หน้ารายการจองและคิวต้องกดอัปเดตเพื่อดึงรายการใหม่; บางหน้ามี polling 10 วินาที และหยุดเมื่อแท็บซ่อน/เปิด dialog/กำลังกรอกข้อมูล Cloudflare เป็นลิงก์ชั่วคราว เปลี่ยนเมื่อเปิดใหม่และต้องเปิดเครื่องค้างไว้
