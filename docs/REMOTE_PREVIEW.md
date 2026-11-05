# ลิงก์ทดสอบจากภายนอก

ใช้ Cloudflare Quick Tunnel สำหรับฐาน Demo ในเครื่อง เปิดหน้าลูกค้าได้ทันทีโดยไม่มีรหัสเปิดลิงก์ ส่วนหน้าจัดการร้านและ API พนักงานยังต้องล็อกอินตามสิทธิ์เดิม ผู้มี URL สามารถเปิดหน้าลูกค้าสาธิตได้

## เปิดลิงก์

หากมี preview.py เดิมเปิดอยู่ ให้หยุดด้วย Ctrl+C ก่อน แล้วดับเบิลคลิก start-preview.command หรือรันจากโฟลเดอร์โปรเจกต์:

```sh
python3 preview.py
```

โปรแกรมแสดง URL `https://….trycloudflare.com` แชร์ URL นี้ได้เลย ไม่ต้องส่งรหัสเปิดลิงก์ ข้อมูล URL รอบปัจจุบันเก็บใน `data/preview-access.json` โดยไม่มี access_code และไม่รวมใน Git

หน้าร้านเข้า `/login` ด้วยบัญชีสาธิต:

- owner / owner1234
- staff / staff1234

เครื่องเจ้าของยังเข้า `http://127.0.0.1:8000` ได้ QR และเอกสาร QR ใช้ HTTPS origin ภายนอกของรอบนี้ การเข้าเครื่องผ่าน localhost ใช้ origin ของเครื่องนั้น

## การทำงานและข้อจำกัด

- ต้องเปิดเครื่อง ต่ออินเทอร์เน็ต และเปิด preview.py ค้างไว้ หยุดด้วย Ctrl+C เริ่มรอบใหม่ URL เปลี่ยน ให้เปิดเอกสาร QR ใหม่สำหรับ URL รอบใหม่
- ใช้ data/demo.sqlite3 เดิม ไม่รีเซ็ตข้อมูล และแยกจาก Presentation สามวันที่ data/presentation.sqlite3 / พอร์ต 8002
- จับล็อกฐานข้อมูล และเปิด listener เฉพาะ 127.0.0.1:8000 สำหรับเครื่องเจ้าของ กับ 127.0.0.1:8001 สำหรับ tunnel ไม่แก้เราเตอร์หรือ firewall
- ตรวจ Host/Origin ตรง URL รอบนั้น ไม่ใช้ wildcard; cookie การล็อกอินผ่าน HTTPS ยังมี Secure/HttpOnly/SameSite=Strict สิทธิ์ owner/staff และข้อจำกัดการพยายามล็อกอินยังทำงาน
- ใช้บัญชีและการชำระจำลองสำหรับ Demo ไม่ใช่ระบบออนไลน์ถาวร ไม่มีการโอนเงินจริง
- โมดูล PreviewAccess ยังเก็บไว้เพื่อความเข้ากันได้และชุดทดสอบเดิม แต่ preview.py ไม่ใช้ประตูรหัสนี้แล้ว

## ตัวเชื่อมที่ใช้

ใช้ cloudflared จากผู้พัฒนาใน .tools/cloudflared หรือที่ติดตั้งใน PATH ชุด GitHub ไม่รวม binary ต้องติดตั้งก่อนใช้ preview.py การ Demo ในเครื่องไม่ต้องติดตั้งตัวเชื่อม

อ้างอิง: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [ดาวน์โหลดจากผู้พัฒนา](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)
