-- V34: each driver / fleet account can carry its own override code. A bag that is
-- not on the trip manifest can only be forced through the pickup scan with that code.
-- Stored hashed (PBKDF2, like the account password). One column per statement.

ALTER TABLE driver_accounts ADD COLUMN override_hash VARCHAR(128) NULL;

ALTER TABLE driver_accounts ADD COLUMN override_salt VARCHAR(64) NULL;
