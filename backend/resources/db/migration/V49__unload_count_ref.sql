-- V49: When bags were scanned at pickup but none at unloading, the driver must type the
--      unloading bag count. unload_count_ref keeps how many bags were pickup-scanned for
--      the request at that moment, so the typed count can be compared (discrepancy).
ALTER TABLE truck_requests ADD COLUMN unload_count_ref INT NULL;
