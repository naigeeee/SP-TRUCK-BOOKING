-- V48: Remarks the driver types on the pickup scan page (scanning app), saved on every
--      truck request of the trip.
ALTER TABLE truck_requests ADD COLUMN pickup_remarks TEXT NULL;
