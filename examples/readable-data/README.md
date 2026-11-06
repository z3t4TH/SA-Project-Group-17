# ข้อมูลสาธิตแบบอ่านได้

ข้อมูลสมมุติวันที่ 3–5 พฤศจิกายน 2026 สร้างใหม่จาก Presentation seed โดยไม่อ่านฐานข้อมูลร้านหรือบัญชีที่เพิ่มในเครื่อง เปิดไฟล์เหล่านี้บน GitHub ได้โดยตรง:

- [demo-readable.sql](demo-readable.sql): โครงสร้าง 20 ตาราง, Primary Key / Foreign Key และ INSERT ข้อมูล
- [Reservations.csv](Reservations.csv): การจอง
- [Queues.csv](Queues.csv): คิว Walk-in
- [Tables.csv](Tables.csv): โต๊ะอาหาร
- [Orders.csv](Orders.csv), [OrderItems.csv](OrderItems.csv), [OrderBatches.csv](OrderBatches.csv): บิล รายการอาหาร และสถานะครัว
- [Payments.csv](Payments.csv), [DailySettlements.csv](DailySettlements.csv), [DailyWages.csv](DailyWages.csv): ชำระเงิน ปิดบัญชี และค่าแรง
- ตารางที่เหลืออยู่ในไฟล์ CSV ชื่อตรงกับตาราง ดูจำนวนแถวใน [manifest.json](manifest.json)

จำนวนเงินเป็น **สตางค์** เช่น 6000 หมายถึง 60 บาท CSV เป็น UTF-8 และใช้เพื่ออ่านข้อมูล; SQL เก็บ constraints และความสัมพันธ์ครบ

นี่คือ **snapshot สำหรับตรวจอ่าน ไม่อัปเดตตามการจองใหม่** โปรแกรมยังเขียนข้อมูลลง `data/<mode>.sqlite3` ตามโหมดที่เปิดอยู่ ไม่เขียนลง CSV หรือ SQL เหล่านี้

เพื่อความปลอดภัย ชุดนี้ปิดการเข้าสู่ระบบ ล้าง Sessions / Requests / AuditLog แทนรหัส QR ด้วยข้อความตัวอย่าง และล้าง payload งานพิมพ์ แต่คง ID ที่ถูกอ้างอิงไว้ จึงไม่ควรนำไปแทนฐานสำหรับเปิดแอป ให้ใช้ `python3 manage.py seed-presentation` สำหรับ Demo ที่ทำงานจริง

สร้างไฟล์ตัวอย่างใหม่จากโฟลเดอร์โปรเจกต์ (macOS/Linux):

```sh
python3 tools/export_readable_demo.py
```

คำสั่งนี้สร้างจาก seed ในพื้นที่ชั่วคราว ไม่แตะฐาน demo/live/presentation เดิม และตรวจนำ SQL กลับเข้า SQLite รวม integrity, foreign keys และยอดบัญชีก่อนส่งออก

หากต้องการตรวจด้วย SQLite ให้สร้าง **ฐานใหม่สำหรับอ่านเท่านั้น**:

```sh
sqlite3 /tmp/sa-inspection.sqlite3 < examples/readable-data/demo-readable.sql
sqlite3 /tmp/sa-inspection.sqlite3 'PRAGMA foreign_key_check; SELECT * FROM Reservations;'
```

เลือกชื่อไฟล์ใหม่ที่ยังไม่มีอยู่เพื่อหลีกเลี่ยงการชนตารางเดิม
