-- V33: nigel.ng@ninjavan.co moves from the Vendor role back to master admin.

UPDATE users
SET role = 'master_admin'
WHERE email = 'nigel.ng@ninjavan.co';
