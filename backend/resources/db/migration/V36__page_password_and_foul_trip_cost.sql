-- V36: common password in front of the protected pages (Driver / Fleet Accounts,
--      Rate Management, Cost Analysis, Trip Utilisation Review, Vendor Speed
--      Performance), its append-only access log, and Foul Trips without Actual Cost.

-- One row (id = 1): the page password, set / changed / reset by the master admin.
CREATE TABLE page_lock (
    id INT NOT NULL PRIMARY KEY,
    password_hash VARCHAR(128) NULL,
    password_salt VARCHAR(64) NULL,
    updated_by VARCHAR(255) NULL,
    updated_at DATETIME NULL
);

-- Append-only log: password set / changed / reset and every protected-page unlock
-- (granted, wrong password, blocked). The app has no route that edits or deletes it.
CREATE TABLE page_lock_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(40) NOT NULL,
    page VARCHAR(60) NULL,
    page_name VARCHAR(120) NULL,
    user_email VARCHAR(255) NULL,
    user_name VARCHAR(255) NULL,
    user_role VARCHAR(120) NULL,
    detail VARCHAR(500) NULL,
    ip_address VARCHAR(64) NULL,
    created_at DATETIME NOT NULL,
    KEY idx_page_lock_logs_created (created_at)
);

-- A Foul Trip carries no Actual Cost; it is charged through the Foul Trip Cost.
UPDATE truck_requests SET actual_cost = 0 WHERE status_id = 7 AND actual_cost <> 0;
