-- Give admin and master_admin the new Vendor Truck Assignment page by default.
-- Config is a JSON column (V5); add the page only when it is not already listed.
UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.admin', 'vendor-trucks')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.admin') = 1
  AND NOT JSON_CONTAINS(config, '"vendor-trucks"', '$.admin');

UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.master_admin', 'vendor-trucks')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.master_admin') = 1
  AND NOT JSON_CONTAINS(config, '"vendor-trucks"', '$.master_admin');
