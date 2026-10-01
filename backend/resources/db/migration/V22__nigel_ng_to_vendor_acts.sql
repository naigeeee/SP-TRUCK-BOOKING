-- V22: nigel.ng@ninjavan.co moves to the Vendor - ACTS role.
-- A vendor role only resolves when a vendor of that name exists, so create the
-- ACTS vendor first when it is missing (no-op when it already exists).

INSERT INTO vendors (name, is_active)
SELECT 'ACTS', TRUE
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM vendors WHERE LOWER(TRIM(name)) = 'acts');

UPDATE users
SET role = 'Vendor - ACTS'
WHERE email = 'nigel.ng@ninjavan.co';
