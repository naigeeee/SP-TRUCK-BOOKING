-- V29: Capacity Conversion (base packaging unit + per-type factors),
--      truck-type max capacity in base units, immutable initial quantity
--      on each request, and the new Trip Utilisation Review page.

CREATE TABLE capacity_conversion (
    id INT NOT NULL PRIMARY KEY,
    config JSON NOT NULL,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO capacity_conversion (id, config)
SELECT 1, JSON_OBJECT(
    'base_packaging_type_id', MIN(id),
    'factors', JSON_OBJECT()
)
FROM packaging_types;

ALTER TABLE truck_types ADD COLUMN max_capacity_units DECIMAL(12,4) NULL DEFAULT NULL;

UPDATE truck_types tt
SET max_capacity_units = (
    SELECT c.max_quantity FROM truck_type_capacities c
    WHERE c.truck_type_id = tt.id
      AND c.packaging_type_id = (SELECT MIN(id) FROM packaging_types)
    ORDER BY c.id LIMIT 1)
WHERE tt.max_capacity_units IS NULL;

ALTER TABLE truck_requests ADD COLUMN initial_quantity INT NULL DEFAULT NULL;

UPDATE truck_requests SET initial_quantity = quantity WHERE initial_quantity IS NULL;

-- Give admin and master_admin the new Trip Utilisation Review page by default.
UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.admin', 'trip-utilisation')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.admin') = 1
  AND NOT JSON_CONTAINS(config, '"trip-utilisation"', '$.admin');

UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.master_admin', 'trip-utilisation')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.master_admin') = 1
  AND NOT JSON_CONTAINS(config, '"trip-utilisation"', '$.master_admin');
