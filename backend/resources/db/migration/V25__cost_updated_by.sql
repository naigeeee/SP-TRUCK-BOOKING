-- V25: track who last edited a request's costs.

ALTER TABLE truck_requests
    ADD COLUMN cost_updated_by VARCHAR(255) NULL DEFAULT NULL;
