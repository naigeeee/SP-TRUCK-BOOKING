-- V20: backfill Final Call Datetime into truck history rows archived before it was captured.

UPDATE truck_request_history h
JOIN truck_requests r ON r.id = h.truck_request_id
SET h.final_call_datetime = r.final_call_datetime
WHERE h.final_call_datetime IS NULL;
