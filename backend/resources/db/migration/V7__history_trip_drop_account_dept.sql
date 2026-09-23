-- Extra History columns: trip ID, drop #, account, department, updated by
ALTER TABLE truck_request_history
    ADD COLUMN trip_id VARCHAR(50) NULL,
    ADD COLUMN drop_sequence INT NULL,
    ADD COLUMN account_id BIGINT NULL,
    ADD COLUMN department_id BIGINT NULL,
    ADD COLUMN updated_by VARCHAR(255) NULL;

UPDATE truck_request_history h
JOIN truck_requests r ON r.id = h.truck_request_id
SET h.account_id = r.account_id,
    h.department_id = r.department_id,
    h.updated_by = r.updated_by,
    h.drop_sequence = r.drop_sequence;
