# โครงสร้าง MVC

| ส่วน | โค้ดจริง | หน้าที่ |
|---|---|---|
| Model facade | models/restaurant.py: Restaurant | สิทธิ์ ธุรกรรม idempotency audit และการอ่านข้อมูล |
| Entity | models/entities.py | ข้อมูลที่มีชนิดชัดเจน และกฎสถานะ/เงิน |
| Model operations | models/operations/*.py | คำสั่งธุรกิจ 23 commands และ SQL ใน transaction ร่วม |
| Controller | controllers/http_controller.py: RestaurantController | HTTP, Host/Origin, session, routing และ response |
| Use-case controllers | controllers/managers.py | CommandRouter และ Manager 13 คลาส |
| Browser View | static/views.js | Boundary classes 18 คลาสสำหรับ render |
| Browser events | static/app.js | เหตุการณ์ ตะกร้า และ HTTP API |
| Document View | views/documents.py: RestaurantView | ใบคิว QR ใบครัว ใบเสร็จ และรายงาน HTML |
| Demo fixtures | models/presentation.py | สร้าง/ตรวจข้อมูลสามวันและวันจำลอง โดยไม่เปลี่ยนกฎธุรกิจ |
| Menu assets | models/menu_images.py, assets/menu/ | catalog ที่เจ้าของยืนยัน ภาพประกอบและเครดิต |

ลำดับคำสั่งเขียน: Browser → RestaurantController → CommandRouter → Manager → Restaurant.mutate → Operations → Entity/SQLite แล้วส่งผลกลับ ทุก mutation commit audit และ idempotency พร้อมธุรกรรมธุรกิจ Operations ไม่ commit เอง

งานอ่านหน้า reports ผ่าน ReportManager.workspace → Restaurant.snapshot ส่วนเอกสารพิมพ์ผ่าน ReportManager.loadReport → Restaurant.report_data → RestaurantView.render_report

service.py และ menu_catalog.py ที่ root เป็น import facade รองรับผู้เรียกและชุดทดสอบเดิม ต้องเก็บไว้ ไม่ใช่ไฟล์ซ้ำที่ลบได้

การเตรียม Presentation เพิ่มโมดูลฟังก์ชัน ไม่ได้เปลี่ยนชื่อคลาสเดิม ไม่เปลี่ยน schema 20 ตาราง เปลี่ยนตำแหน่ง catalog จาก references/menu/catalog.json เป็น assets/menu/catalog.json และเพิ่มข้อมูล menu_images / presentation ใน GET /api/config ส่วนรายงานและเครื่องมือวาดแผนภาพเก่าแยกเก็บใน private archive ตาม CLEANUP.md

ภาพเมนูจับคู่ด้วย MenuCatalog.source_key ผ่าน menu_images.by_key (157 รายการ) และสำรองด้วยชื่อเมนู การแก้ชื่อเดิมไม่ทำให้ภาพหาย Guest menu ส่ง catalog_key เพิ่มด้วย ไม่มีการเปลี่ยน schema หรือชื่อคลาส

งาน QA เพิ่ม RestaurantHTTPServer ใน controllers/http_controller.py เป็น infrastructure class สืบทอด ThreadingHTTPServer เพื่อกำหนด backlog=64 ใช้ใน app.py / preview.py ไม่เปลี่ยนชื่อคลาสธุรกิจหรือ schema; เพิ่ม calendar_date สำหรับตรวจวันที่ก่อนอ่านรายงาน
