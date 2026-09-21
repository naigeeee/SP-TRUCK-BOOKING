-- Add latitude and longitude columns to ports table
ALTER TABLE ports ADD COLUMN latitude DECIMAL(10, 7) NULL AFTER location;
ALTER TABLE ports ADD COLUMN longitude DECIMAL(10, 7) NULL AFTER latitude;
