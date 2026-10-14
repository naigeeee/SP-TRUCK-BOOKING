-- V37: remarks the driver / fleet types at the drop (with the photos) before
--      Finish Drop. Shown on the Masterlist as "Unloading Remarks".
ALTER TABLE truck_requests ADD COLUMN unloading_remarks VARCHAR(1000) NULL;
