CREATE TABLE OrderBatches(
 batch_id INTEGER PRIMARY KEY,
 order_id INTEGER NOT NULL REFERENCES Orders(order_id),
 status TEXT NOT NULL DEFAULT 'RECEIVED' CHECK(status IN ('RECEIVED','PREPARING','READY','SERVED')),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 updated_by INTEGER REFERENCES Users(user_id),
 kitchen_job_id INTEGER UNIQUE REFERENCES PrintJobs(job_id),
 legacy INTEGER NOT NULL DEFAULT 0 CHECK(legacy IN (0,1))
);
CREATE INDEX batch_status_order ON OrderBatches(status,order_id);
CREATE TABLE OrderBatchItems(
 batch_id INTEGER NOT NULL REFERENCES OrderBatches(batch_id),
 order_item_id INTEGER NOT NULL UNIQUE REFERENCES OrderItems(order_item_id),
 PRIMARY KEY(batch_id,order_item_id)
);
CREATE TABLE OrderBatchEvents(
 event_id INTEGER PRIMARY KEY,
 batch_id INTEGER NOT NULL REFERENCES OrderBatches(batch_id),
 from_status TEXT,to_status TEXT NOT NULL,
 user_id INTEGER REFERENCES Users(user_id),created_at TEXT NOT NULL
);
