-- V27: nigel.ng@ninjavan.co moves to the Vendor - NJV role.
-- A vendor role only resolves when a vendor of that name exists, so create the
-- NJV vendor first when it is missing (no-op when it already exists).

INSERT INTO vendors (name, is_active)
SELECT 'NJV', TRUE
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM vendors WHERE LOWER(TRIM(name)) = 'njv');

UPDATE users
SET role = 'Vendor - NJV'
WHERE email = 'nigel.ng@ninjavan.co';
