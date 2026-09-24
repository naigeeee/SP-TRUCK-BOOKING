-- Persist Trip ID on truck_requests so terminal rows keep their generation
-- and are not re-merged when the same truck is reused for a later trip.
ALTER TABLE truck_requests
    ADD COLUMN trip_id VARCHAR(50) NULL;

-- Do not blindly copy history.trip_id: it can already be wrong when two
-- generations were merged. Leave NULL so runtime groups terminal rows by
-- account and freezes new IDs at allocation.
