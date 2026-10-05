-- V28: nigel.ng@ninjavan.co moves back to the master admin role (leaves the NJV vendor role).

UPDATE users
SET role = 'master_admin'
WHERE email = 'nigel.ng@ninjavan.co';
