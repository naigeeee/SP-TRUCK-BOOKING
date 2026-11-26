-- V46: In-website alerts. The same alerts that go to Google Chat can also pop up inside
--      the website for users who have it open. Who gets each alert is set per alert and
--      per role on the Google Chat Alerts page (kept in app_settings, key "web_alerts").

-- One row per in-website alert, with the roles it was meant for (vendor users only see
-- alerts for their own vendor's trips). Rows older than 7 days are deleted by the app.
CREATE TABLE web_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(40) NOT NULL,
    trip_id VARCHAR(64) NULL,
    request_number VARCHAR(64) NULL,
    request_id INT NULL,
    vendor_id INT NULL,
    roles VARCHAR(255) NULL,
    target_email VARCHAR(255) NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NULL,
    created_at DATETIME NOT NULL,
    KEY idx_web_alerts_created (created_at)
);

-- What each user has read: every alert up to this id.
CREATE TABLE web_alert_reads (
    user_email VARCHAR(255) NOT NULL PRIMARY KEY,
    last_read_id BIGINT NOT NULL DEFAULT 0,
    updated_at DATETIME NULL
);
