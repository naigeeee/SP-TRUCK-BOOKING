-- V45: FID on truck requests (optional), and the bag counts a driver types when a request
-- has no manifest and no bags were scanned (end of pickup scan / end of unloading scan).

ALTER TABLE truck_requests ADD COLUMN fid VARCHAR(100) NULL;
ALTER TABLE truck_requests ADD COLUMN pickup_manual_count INT NULL;
ALTER TABLE truck_requests ADD COLUMN unload_manual_count INT NULL;
