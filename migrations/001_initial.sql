PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS Settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Tables(
 table_id INTEGER PRIMARY KEY,table_number TEXT NOT NULL UNIQUE,
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 20),
 status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(status IN ('AVAILABLE','HELD','OCCUPIED')));
CREATE TABLE IF NOT EXISTS Reservations(
 reservation_id INTEGER PRIMARY KEY,reservation_code TEXT NOT NULL UNIQUE,
 customer_name TEXT NOT NULL,phone_number TEXT NOT NULL,reservation_datetime TEXT NOT NULL,
 guest_count INTEGER NOT NULL CHECK(guest_count BETWEEN 1 AND 20),
 status TEXT NOT NULL DEFAULT 'CONFIRMED' CHECK(status IN ('CONFIRMED','CHECKED_IN','CANCELLED','NO_SHOW')),
 table_id INTEGER REFERENCES Tables(table_id),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS reservation_slot ON Reservations(reservation_datetime,status);
CREATE TABLE IF NOT EXISTS Queues(
 queue_id INTEGER PRIMARY KEY,queue_number INTEGER NOT NULL,service_date TEXT NOT NULL,
 customer_name TEXT NOT NULL,phone_number TEXT NOT NULL,guest_count INTEGER NOT NULL CHECK(guest_count BETWEEN 1 AND 20),
 status TEXT NOT NULL DEFAULT 'WAITING' CHECK(status IN ('WAITING','CALLED','SEATED','SKIPPED','CANCELLED')),
 call_count INTEGER NOT NULL DEFAULT 0 CHECK(call_count BETWEEN 0 AND 3),
 table_id INTEGER REFERENCES Tables(table_id),created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 UNIQUE(service_date,queue_number));
CREATE TABLE IF NOT EXISTS MenuItems(
 menu_id INTEGER PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,
 price INTEGER NOT NULL CHECK(price>=0),is_available INTEGER NOT NULL CHECK(is_available IN (0,1)));
CREATE TABLE IF NOT EXISTS Orders(
 order_id INTEGER PRIMARY KEY,session_token TEXT NOT NULL UNIQUE,opened_at TEXT NOT NULL,closed_at TEXT,
 total_amount INTEGER NOT NULL DEFAULT 0 CHECK(total_amount>=0),is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
 table_id INTEGER NOT NULL REFERENCES Tables(table_id));
CREATE UNIQUE INDEX IF NOT EXISTS one_active_order ON Orders(table_id) WHERE is_active=1;
CREATE TABLE IF NOT EXISTS OrderItems(
 order_item_id INTEGER PRIMARY KEY,quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 99),
 item_price INTEGER NOT NULL CHECK(item_price>=0),name_snapshot TEXT NOT NULL,note TEXT NOT NULL,
 ordered_at TEXT NOT NULL,order_id INTEGER NOT NULL REFERENCES Orders(order_id),
 menu_id INTEGER NOT NULL REFERENCES MenuItems(menu_id));
CREATE TABLE IF NOT EXISTS Staff(
 staff_id INTEGER PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,
 daily_rate INTEGER NOT NULL CHECK(daily_rate>=0),phone_number TEXT NOT NULL DEFAULT '',
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)));
CREATE TABLE IF NOT EXISTS Users(
 user_id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('OWNER','STAFF')),name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Sessions(
 token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES Users(user_id),expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS DailySettlements(
 settlement_id INTEGER PRIMARY KEY,settlement_date TEXT NOT NULL UNIQUE,
 total_sales INTEGER NOT NULL,material_cost INTEGER NOT NULL CHECK(material_cost>=0),labor_cost INTEGER NOT NULL CHECK(labor_cost>=0),
 net_profit_loss INTEGER NOT NULL,previous_loss INTEGER NOT NULL,accumulated_loss INTEGER NOT NULL CHECK(accumulated_loss>=0),
 distributable_profit INTEGER NOT NULL CHECK(distributable_profit>=0),partner_shares TEXT NOT NULL,
 expected_cash INTEGER NOT NULL,actual_cash INTEGER NOT NULL CHECK(actual_cash>=0),cash_difference INTEGER NOT NULL,
 difference_note TEXT NOT NULL,closed_by INTEGER NOT NULL REFERENCES Users(user_id),closed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Payments(
 payment_id INTEGER PRIMARY KEY,payment_method TEXT NOT NULL CHECK(payment_method IN ('CASH','MOCK_QR')),
 total_paid INTEGER NOT NULL CHECK(total_paid>0),amount_received INTEGER NOT NULL,change_amount INTEGER NOT NULL CHECK(change_amount>=0),
 payment_time TEXT NOT NULL,order_id INTEGER NOT NULL UNIQUE REFERENCES Orders(order_id),
 settlement_id INTEGER REFERENCES DailySettlements(settlement_id),received_by INTEGER NOT NULL REFERENCES Users(user_id),
 CHECK(amount_received=total_paid+change_amount));
CREATE TABLE IF NOT EXISTS DailyWages(
 wage_id INTEGER PRIMARY KEY,settlement_id INTEGER NOT NULL REFERENCES DailySettlements(settlement_id),
 staff_id INTEGER NOT NULL REFERENCES Staff(staff_id),name_snapshot TEXT NOT NULL,
 wage_amount INTEGER NOT NULL CHECK(wage_amount>=0),recorded_at TEXT NOT NULL,UNIQUE(settlement_id,staff_id));
CREATE TABLE IF NOT EXISTS AuditLog(
 audit_id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,entity_id TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Requests(
 request_key TEXT NOT NULL,scope TEXT NOT NULL,body_hash TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(scope,request_key));
CREATE TABLE IF NOT EXISTS PrintJobs(
 job_id INTEGER PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('QUEUE','SESSION','KITCHEN','RECEIPT')),
 payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','PRINTED','FAILED')),
 attempts INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS lock_payment_update BEFORE UPDATE ON Payments WHEN OLD.settlement_id IS NOT NULL
 BEGIN SELECT RAISE(ABORT,'settled payment is immutable'); END;
CREATE TRIGGER IF NOT EXISTS lock_payment_delete BEFORE DELETE ON Payments
 BEGIN SELECT RAISE(ABORT,'payment history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS lock_settlement_update BEFORE UPDATE ON DailySettlements
 BEGIN SELECT RAISE(ABORT,'settlement is immutable'); END;
CREATE TRIGGER IF NOT EXISTS lock_settlement_delete BEFORE DELETE ON DailySettlements
 BEGIN SELECT RAISE(ABORT,'settlement is immutable'); END;
PRAGMA user_version=1;
