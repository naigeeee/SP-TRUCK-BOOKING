-- V17: nigel.ng@ninjavan.co moves from Master Admin to the Vendor - 11E role.

UPDATE users
SET role = 'Vendor - 11E'
WHERE email = 'nigel.ng@ninjavan.co' AND role = 'master_admin';
