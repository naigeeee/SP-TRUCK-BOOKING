-- V43: optional contact person and receiving hours for ports, plus who last
-- changed each port and when (shown in Master Library > Ports).
-- Receiving hours are stored as 'HH:MM' (24-hour) text.

ALTER TABLE ports ADD COLUMN contact_pic_name VARCHAR(255) NULL;
ALTER TABLE ports ADD COLUMN contact_pic_number VARCHAR(64) NULL;
ALTER TABLE ports ADD COLUMN receiving_from VARCHAR(5) NULL;
ALTER TABLE ports ADD COLUMN receiving_to VARCHAR(5) NULL;
ALTER TABLE ports ADD COLUMN updated_by VARCHAR(255) NULL;
ALTER TABLE ports ADD COLUMN updated_at DATETIME NULL;
