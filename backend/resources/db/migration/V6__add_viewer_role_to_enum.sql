-- Add 'viewer' to the role ENUM so new users can be auto-created with viewer role
ALTER TABLE users MODIFY COLUMN role ENUM('master_admin', 'admin', 'normal_user', 'viewer') NOT NULL DEFAULT 'normal_user';
