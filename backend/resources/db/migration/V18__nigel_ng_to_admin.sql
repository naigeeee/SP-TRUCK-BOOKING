-- V18: nigel.ng@ninjavan.co moves to the admin role.

UPDATE users
SET role = 'admin'
WHERE email = 'nigel.ng@ninjavan.co';
