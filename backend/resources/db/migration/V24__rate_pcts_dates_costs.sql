-- V24: rate foul/fuel percentages, foul/cancellation dates, additional cost columns.

ALTER TABLE vendor_rates
    ADD COLUMN foul_trip_pct DECIMAL(5,2) NULL,
    ADD COLUMN fuel_surcharge_pct DECIMAL(5,2) NULL;

ALTER TABLE truck_requests
    ADD COLUMN foul_trip_date DATE NULL,
    ADD COLUMN cancellation_date DATE NULL;

ALTER TABLE truck_requests
    ADD COLUMN toll_fee DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN management_fee DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN fuel DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN parking DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN miscellaneous DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN manpower DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN toll DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN welfare DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN wh_rental DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN toll_fee_easytrip DECIMAL(12,2) NULL DEFAULT 0,
    ADD COLUMN toll_fee_autosweep DECIMAL(12,2) NULL DEFAULT 0;
