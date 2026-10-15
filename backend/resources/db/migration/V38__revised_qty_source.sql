-- V38: which event set the Revised Qty last: 'manual' (Qty typed in New Request /
--      Edit), 'manifest' (manifest uploaded) or 'unload' (unloading scan ended).
--      NULL = set before this rule: completed unloading scan, else manifest IDs, else Qty.
ALTER TABLE truck_requests ADD COLUMN revised_qty_src VARCHAR(16) NULL;
