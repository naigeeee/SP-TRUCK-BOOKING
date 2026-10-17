-- V39: Google Chat alerts (webhook + on/off per alert, kept in app_settings, and a
--      log of every alert sent / failed) and the Storage Usage page (Google Sheet
--      size reported by the Apps Script after each sync).

-- Small key/value settings changed by the master admin in the app.
CREATE TABLE app_settings (
    setting_key VARCHAR(64) NOT NULL PRIMARY KEY,
    setting_value TEXT NULL,
    updated_by VARCHAR(255) NULL,
    updated_at DATETIME NULL
);

-- One row per Google Chat alert: sent, failed (with the reason) or skipped (no webhook).
CREATE TABLE chat_alert_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(40) NOT NULL,
    trip_id VARCHAR(64) NULL,
    request_number VARCHAR(64) NULL,
    status VARCHAR(16) NOT NULL,
    detail VARCHAR(500) NULL,
    created_at DATETIME NOT NULL,
    KEY idx_chat_alert_log_created (created_at)
);

-- One row per Google Sheets sync: how many cells the spreadsheet has (Google caps a
-- spreadsheet at 10 million cells) so growth can be followed on the Storage Usage page.
CREATE TABLE sheet_usage_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    spreadsheet_name VARCHAR(255) NULL,
    spreadsheet_url VARCHAR(500) NULL,
    total_cells BIGINT NOT NULL DEFAULT 0,
    used_cells BIGINT NOT NULL DEFAULT 0,
    sheet_count INT NOT NULL DEFAULT 0,
    tabs_json TEXT NULL,
    created_at DATETIME NOT NULL,
    KEY idx_sheet_usage_log_created (created_at)
);
