-- V16: legacy "Allocated" rows that already carry a truck plate and a vendor
-- are really already on the road -- promote them to In Transit (status 3).

UPDATE truck_requests tr
JOIN trucks tk ON tr.assigned_truck_id = tk.id
SET tr.status_id = 3
WHERE tr.status_id = 2
  AND tk.plate_number IS NOT NULL AND tk.plate_number <> ''
  AND COALESCE(tk.vendor_id, tr.vendor_id) IS NOT NULL;
