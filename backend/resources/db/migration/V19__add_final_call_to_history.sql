-- V19: fleet history records the Final Call datetime.

ALTER TABLE truck_request_history ADD COLUMN final_call_datetime DATETIME NULL;
