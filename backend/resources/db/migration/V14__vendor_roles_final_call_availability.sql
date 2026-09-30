-- V14: dynamic vendor roles, final call datetime, manual truck availability.
-- One statement per change; no column+FK in a single ALTER.

ALTER TABLE users MODIFY COLUMN role VARCHAR(64) NOT NULL DEFAULT 'normal_user';

ALTER TABLE truck_requests ADD COLUMN vendor_id BIGINT NULL;

ALTER TABLE truck_requests ADD COLUMN final_call_datetime DATETIME NULL;

ALTER TABLE trucks ADD COLUMN is_available TINYINT(1) NOT NULL DEFAULT 1;

-- Backfill: requests already allocated to a truck inherit that truck's vendor.
UPDATE truck_requests tr LEFT JOIN trucks tk ON tr.assigned_truck_id = tk.id
    SET tr.vendor_id = tk.vendor_id
    WHERE tr.vendor_id IS NULL AND tk.vendor_id IS NOT NULL;
