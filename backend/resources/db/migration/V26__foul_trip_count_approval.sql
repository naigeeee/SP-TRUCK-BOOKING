-- V26: Foul Trip Count Confirmation and the green-tick Foul Trip approval trail.

ALTER TABLE truck_requests
    ADD COLUMN foul_trip_count INT NULL DEFAULT NULL;

ALTER TABLE truck_requests
    ADD COLUMN foul_trip_approved_by VARCHAR(255) NULL DEFAULT NULL;

ALTER TABLE truck_requests
    ADD COLUMN foul_trip_approved_at DATETIME NULL DEFAULT NULL;

-- Give admin and master_admin the Foul Trip Review page by default.
-- Config is a JSON column (V5); add the page only when it is not already listed.
UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.admin', 'foul-trip-review')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.admin') = 1
  AND NOT JSON_CONTAINS(config, '"foul-trip-review"', '$.admin');

UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.master_admin', 'foul-trip-review')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.master_admin') = 1
  AND NOT JSON_CONTAINS(config, '"foul-trip-review"', '$.master_admin');
