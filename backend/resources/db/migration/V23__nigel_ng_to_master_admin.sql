-- V23: nigel.ng@ninjavan.co moves to the master_admin role.

UPDATE users
SET role = 'master_admin'
WHERE email = 'nigel.ng@ninjavan.co';
