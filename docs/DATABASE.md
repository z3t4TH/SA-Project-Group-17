# ฐานข้อมูลเชิงสัมพันธ์ของระบบร้านอาหาร

ระบบใช้ SQLite เก็บข้อมูลเป็นตารางจริง พร้อม Primary Key, Foreign Key และ SQL transactions ไฟล์ .sqlite3 เป็นรูปแบบจัดเก็บของฐานข้อมูล การเป็นไฟล์ binary ไม่ได้เปลี่ยนโครงสร้างเชิงสัมพันธ์ให้กลายเป็นไฟล์ข้อความหรือ JSON

| โหมด | ไฟล์ฐานข้อมูล |
|---|---|
| Demo / Cloudflare ผ่าน preview.py | data/demo.sqlite3 |
| Presentation สามวัน | data/presentation.sqlite3 |
| ข้อมูลจริง | data/live.sqlite3 |

## ตารางและโครงสร้าง

- **AuditLog**
- **DailySettlements** — closed_by → Users.user_id
- **DailyWages** — staff_id → Staff.staff_id, settlement_id → DailySettlements.settlement_id
- **MenuCatalog** — menu_id → MenuItems.menu_id
- **MenuItems**
- **OrderBatchEvents** — user_id → Users.user_id, batch_id → OrderBatches.batch_id
- **OrderBatchItems** — order_item_id → OrderItems.order_item_id, batch_id → OrderBatches.batch_id
- **OrderBatches** — kitchen_job_id → PrintJobs.job_id, updated_by → Users.user_id, order_id → Orders.order_id
- **OrderItems** — menu_id → MenuItems.menu_id, order_id → Orders.order_id
- **Orders** — table_id → Tables.table_id
- **Payments** — received_by → Users.user_id, settlement_id → DailySettlements.settlement_id, order_id → Orders.order_id
- **PrintJobs**
- **Queues** — table_id → Tables.table_id
- **Requests**
- **Reservations** — table_id → Tables.table_id
- **Sessions** — user_id → Users.user_id
- **Settings**
- **Staff**
- **Tables**
- **Users**

การจองล่วงหน้าเก็บใน Reservations มี reservation_id เป็น Primary Key และ table_id อ้างถึง Tables.table_id เมื่อจัดโต๊ะแล้ว ส่วนคิว Walk-in เก็บใน Queues แยกกัน ชื่อตาราง Tables หมายถึงโต๊ะอาหาร ไม่ใช่ชื่อตารางการจอง

อ่านโครงสร้าง SQL แบบข้อความได้จาก migrations/001_initial.sql, 002_menu_catalog.sql และ 003_order_batches.sql หรือเปิดฐานด้วยโปรแกรมที่รองรับ SQLite เพื่อดูแต่ละตาราง

## ตัวอย่างตรวจข้อมูลด้วย SQL

```sql
SELECT reservation_id, reservation_code, customer_name,
       reservation_datetime, guest_count, status, table_id
FROM Reservations
ORDER BY reservation_id DESC;

SELECT r.reservation_code, r.guest_count, r.status, t.table_number
FROM Reservations AS r
LEFT JOIN Tables AS t ON t.table_id = r.table_id;

PRAGMA integrity_check;
PRAGMA foreign_key_check;
```

ตรวจฐาน Demo วันที่ 5 พฤศจิกายน 2026: 20 ตาราง, 20 Foreign Keys, integrity_check=ok และไม่พบ foreign_key_check violations ทุก connection ของ Model เปิด PRAGMA foreign_keys=ON

ข้อมูลสมมุติแบบข้อความที่เผยแพร่บน GitHub อยู่ใน [data/readable](../data/readable/README.md) มี SQL พร้อมโครงสร้างและ CSV แยกครบ 20 ตาราง สร้างจาก seed ใหม่โดยไม่อ่านฐานร้าน ล้างข้อมูลเข้าสู่ระบบและรหัส QR แล้ว เหมาะสำหรับตรวจความสัมพันธ์และยอดบัญชี ไม่ใช้แทนฐานเปิดโปรแกรม

ไฟล์ data/demo-readable.sql เดิมเป็น snapshot ส่วนตัว ไม่รวมใน GitHub ข้อมูลใหม่อัปเดตในฐาน .sqlite3 ไม่ได้อัปเดตไฟล์ SQL/CSV โดยอัตโนมัติ

## SQL และ CSV ที่อัปเดตตามการใช้งานในเครื่อง

เมื่อเปิดด้วย app.py หรือ preview.py ระบบส่งออก snapshot เมื่อเริ่มเซิร์ฟเวอร์ และหลัง transaction ที่บันทึกสำเร็จ โดยเขียนไฟล์ใหม่แบบ atomic:

| โหมด | SQL | โฟลเดอร์ CSV แยก 20 ตาราง |
|---|---|---|
| Demo / Cloudflare | data/demo-readable.sql | data/demo-readable/ |
| Presentation | data/presentation-readable.sql | data/presentation-readable/ |
| Live | data/live-readable.sql | data/live-readable/ |

เปิดไฟล์ด้วย text editor แล้วโหลดไฟล์ใหม่หลังทำรายการเพื่อเห็นข้อมูลล่าสุด SQLite ยังคงเป็นฐานหลัก ไฟล์ SQL สำหรับตรวจอ่านเท่านั้น ไม่มี password hash, session, response ของคำขอ, audit หรือ payload งานพิมพ์ และแทนรหัส QR ด้วยข้อความตัวอย่าง จึงไม่ใช้ SQL นี้เปิดแอปแทนฐานเดิม

ไฟล์ยังมีชื่อลูกค้า เบอร์โทร และข้อมูลธุรกรรม จึงเก็บไว้เฉพาะเครื่อง ตั้งสิทธิ์เจ้าของอ่าน/เขียน และถูก .gitignore กันไว้ ไม่อัปโหลดอัตโนมัติ ส่วน data/readable/demo-readable.sql บน GitHub ยังคงเป็นข้อมูลสมมุติจาก seed ไม่ถูกเขียนทับด้วยข้อมูลร้าน

ถ้าส่งออกไม่สำเร็จ ระบบแจ้ง error ใน Terminal และคงไฟล์ก่อนหน้าไว้ ธุรกรรมที่บันทึกสำเร็จจะไม่ถูกยกเลิก เปิดระบบใหม่หรือทำรายการครั้งต่อไปเพื่อส่งออกใหม่ การแก้ฐานด้วยเครื่องมือภายนอกจะส่งออกเมื่อเริ่มระบบหรือมี transaction ครั้งถัดไป

CSV เช่น Reservations.csv อัปเดตทุกครั้งพร้อม SQL จาก snapshot เดียวกัน เปิดไฟล์ใหม่หรือ Reload ใน editor หลังทำรายการ แต่ละไฟล์ถูกแทนที่แบบ atomic; หากต้องอ่านหลายตารางให้ตรงกันระหว่างมีรายการเข้าพร้อมกัน ใช้ SQL ไฟล์เดียว เนื่องจาก CSV หลายไฟล์ไม่ได้ถูกแทนที่พร้อมกันทั้งโฟลเดอร์ จำนวนเงินเก็บเป็นสตางค์ CSV เหล่านี้เป็นข้อมูลภายในเช่นเดียวกับ SQL และไม่ขึ้น GitHub
