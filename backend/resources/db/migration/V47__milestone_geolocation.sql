-- V47: Where the driver was for each scanning-app milestone (Arrived Pickup, Start
--      Loading, End Loading, Arrived Destination, Start Unloading, End Unloading).
--      One JSON object per truck request, e.g.
--      {"arrived_pickup_datetime": {"lat": 14.2051, "lng": 121.1397, "acc": 12,
--        "addr": "...", "at": "2026-11-24 00:50:00"}}
--      or {"status": "denied"} when the phone's location was off or refused.
ALTER TABLE truck_requests ADD COLUMN milestone_geo TEXT NULL;
