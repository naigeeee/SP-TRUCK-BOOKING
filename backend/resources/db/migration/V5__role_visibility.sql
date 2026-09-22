CREATE TABLE IF NOT EXISTS role_visibility (
    id BIGINT PRIMARY KEY DEFAULT 1,
    config JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT IGNORE INTO role_visibility (id, config) VALUES (1, '{"viewer":["dashboard","masterlist"],"normal_user":["dashboard","new-request","masterlist","pending"],"admin":["dashboard","new-request","masterlist","pending","fleet","rates","evaluation","cost","library","users","role-visibility"],"master_admin":["dashboard","new-request","masterlist","pending","fleet","rates","evaluation","cost","library","users","role-visibility"]}');
