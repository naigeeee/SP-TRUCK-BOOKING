-- V41: keep an encrypted copy of the page password so the master admin can show it on
--      Page Password & Logs (masked until they tick "Show password"; every reveal is
--      logged). The key is derived from the platform's JWT_SECRET, never stored here.
--      Passwords set before this release have no copy: reset once to make it showable.
ALTER TABLE page_lock ADD COLUMN password_enc TEXT NULL;
