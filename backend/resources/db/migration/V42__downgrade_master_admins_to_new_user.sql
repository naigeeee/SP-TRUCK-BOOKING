-- V42: take access away from these 7 Master Admins by setting them to New User
-- (New User has no pages). Only rows that are still master_admin are changed;
-- an email that does not exist in a database is simply skipped.
-- Note: this runs in every environment the migration is deployed to.

UPDATE users
SET role = 'new_user'
WHERE role = 'master_admin'
  AND email IN (
    'adriankurt.feliciano@ninjavan.co',
    'arjhay.mariano@ninjavan.co',
    'carvy.labapez@ninjavan.co',
    'junyi.ang@ninjavan.co',
    'melvyn.ong@ninjavan.co',
    'rachel.tan@ninjavan.co',
    'yeoh.enghong@ninjavan.co'
  );
