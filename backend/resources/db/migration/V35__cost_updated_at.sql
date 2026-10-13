-- V35: when the costs of a request were last changed (shown as "Updated At" beside
-- "Updated By" on Cost Analysis). Existing cost edits take the request's last update time.

ALTER TABLE truck_requests ADD COLUMN cost_updated_at DATETIME NULL;

UPDATE truck_requests SET cost_updated_at = updated_at
WHERE cost_updated_by IS NOT NULL AND cost_updated_by <> '' AND cost_updated_at IS NULL;
