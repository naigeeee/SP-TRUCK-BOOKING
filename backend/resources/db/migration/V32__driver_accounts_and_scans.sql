-- V32: Driver / Fleet accounts, the scanning app (pickup sort + unloading),
--      and the driver assignment that replaces truck-number picking.
--
-- One statement per change: no column plus foreign key in a single ALTER,
-- and no self-referencing foreign key with ON DELETE CASCADE.

CREATE TABLE driver_accounts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    vendor_id BIGINT NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    password_salt VARCHAR(64) NOT NULL,
    driver_name VARCHAR(255) NULL,
    driver_phone VARCHAR(50) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    active_trip_id VARCHAR(64) NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_driver_username (username)
);

ALTER TABLE driver_accounts ADD CONSTRAINT fk_driver_accounts_vendor
    FOREIGN KEY (vendor_id) REFERENCES vendors(id);

-- The truck this driver/fleet account drives: choosing the account on the
-- Vendor Truck Assignment page assigns this truck as well as the driver.
ALTER TABLE driver_accounts ADD COLUMN truck_id BIGINT NULL;

ALTER TABLE driver_accounts ADD CONSTRAINT fk_driver_accounts_truck
    FOREIGN KEY (truck_id) REFERENCES trucks(id);

CREATE TABLE driver_sessions (
    token VARCHAR(64) NOT NULL PRIMARY KEY,
    driver_account_id BIGINT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL
);

ALTER TABLE driver_sessions ADD CONSTRAINT fk_driver_sessions_account
    FOREIGN KEY (driver_account_id) REFERENCES driver_accounts(id);

-- Pickup sort: one row per bag scanned while loading. The trip base makes the
-- bag unique across the whole trip, so a second scan of the same bag is caught
-- by the unique index no matter which drop it was expected on.
CREATE TABLE scan_pickup_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trip_base VARCHAR(64) NOT NULL,
    request_id BIGINT NULL,
    bag_id VARCHAR(255) NOT NULL,
    scan_kind VARCHAR(16) NOT NULL DEFAULT 'original',
    scanned_by VARCHAR(255) NULL,
    scanned_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_scan_pickup_bag (trip_base, bag_id)
);

-- Unloading: one row per bag scanned against a request, unique per request.
CREATE TABLE scan_unload_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id BIGINT NOT NULL,
    bag_id VARCHAR(255) NOT NULL,
    scan_kind VARCHAR(16) NOT NULL DEFAULT 'original',
    scanned_by VARCHAR(255) NULL,
    scanned_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_scan_unload_bag (request_id, bag_id)
);

ALTER TABLE truck_requests ADD COLUMN driver_account_id BIGINT NULL;

ALTER TABLE truck_requests ADD COLUMN late_reason TEXT NULL;

ALTER TABLE truck_requests ADD COLUMN pickup_scan_key VARCHAR(64) NULL;

ALTER TABLE truck_requests ADD COLUMN pickup_scan_closed_at DATETIME NULL;

ALTER TABLE truck_requests ADD COLUMN unload_scan_key VARCHAR(64) NULL;

ALTER TABLE truck_requests ADD COLUMN unload_scan_closed_at DATETIME NULL;

-- Give admin and master_admin the Driver / Fleet Accounts page by default.
UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.admin', 'driver-accounts')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.admin') = 1
  AND NOT JSON_CONTAINS(config, '"driver-accounts"', '$.admin');

UPDATE role_visibility
SET config = JSON_ARRAY_APPEND(config, '$.master_admin', 'driver-accounts')
WHERE id = 1
  AND JSON_CONTAINS_PATH(config, 'one', '$.master_admin') = 1
  AND NOT JSON_CONTAINS(config, '"driver-accounts"', '$.master_admin');
