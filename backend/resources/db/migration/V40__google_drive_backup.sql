-- V40: Google Drive backup of attachments, manifests and pickup / unloading scan
--      manifests. The Google Apps Script copies each file into
--      <backup folder> / <final call date, else initial call date> / <request #> /
--      and reports back; these tables remember what is already in Drive.

-- One row per file copied (or tried): which version is in Drive and where.
CREATE TABLE drive_backup_files (
    item_key VARCHAR(64) NOT NULL PRIMARY KEY,
    request_id BIGINT NOT NULL,
    kind VARCHAR(16) NOT NULL,
    version VARCHAR(255) NULL,
    file_name VARCHAR(255) NULL,
    drive_file_id VARCHAR(128) NULL,
    status VARCHAR(16) NOT NULL,
    detail VARCHAR(500) NULL,
    attempts INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL,
    KEY idx_drive_backup_files_request (request_id),
    KEY idx_drive_backup_files_updated (updated_at)
);

-- One row per request folder in Drive and the date folder it sits in, so the folder
-- can be moved when the request's final call date is set or changed.
CREATE TABLE drive_backup_folders (
    request_id BIGINT NOT NULL PRIMARY KEY,
    drive_folder_id VARCHAR(128) NOT NULL,
    date_folder VARCHAR(16) NOT NULL,
    updated_at DATETIME NOT NULL
);
