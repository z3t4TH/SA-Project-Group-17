# Order batches and kitchen/service status

Each successful cart submission creates one `OrderBatches` record with its own stable ID. `Orders` remains the table bill; `OrderItems` are linked to exactly one batch by `OrderBatchItems`. Kitchen printing and billing totals continue to use the same transactional item snapshots.

Staff/owners advance RECEIVED → PREPARING → READY → SERVED using authenticated `batch_status`, with `expected_status` for optimistic conflict detection and existing idempotency keys. Each transition records employee ID and time in `OrderBatchEvents` in the same write transaction. Customers only read batches belonging to their active QR session. Status applies to the whole submission; staff mark served after every item in that batch has reached the table.

Kitchen defaults to all unserved batches and has state/all filters. Pending batches remain visible after a bill is paid or the date changes. Served batches are visible while the bill is open or on their last update date. The customer page has menu/status tabs and selects status after sending a cart. Both views poll every 10 seconds while visible and not editing a field.

Migration 003 is transactional. Existing active submissions are reconstructed from their original kitchen print jobs, not timestamp grouping alone; legacy imports without print jobs are grouped by time. Old batches are explicitly marked for staff verification because their historical preparation state was never recorded. Closed historical bills are preserved without inventing served states. Backup was taken before the demo upgrade.

The temporary external tunnel was restarted for the Python service update. The current URL and gate code are in ignored `data/preview-access.json`; application login credentials remain unchanged. Table QR printouts made with the old temporary hostname must be opened/printed again to use the current link.
