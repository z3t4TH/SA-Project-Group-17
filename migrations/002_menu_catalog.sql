CREATE TABLE IF NOT EXISTS MenuCatalog(
 source_key TEXT PRIMARY KEY,
 menu_id INTEGER NOT NULL UNIQUE REFERENCES MenuItems(menu_id),
 source_hash TEXT NOT NULL,
 review_note TEXT NOT NULL DEFAULT ''
);
PRAGMA user_version=2;
