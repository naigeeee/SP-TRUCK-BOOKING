-- Retarget running sequences: Trip ID uses 5 digits (00001..99999),
-- Request # uses 3 digits per day (001..999). Existing rows from the
-- short-lived 7-digit rollout are resized in place; counts are preserved.
UPDATE id_sequences SET width = 5 WHERE seq_key = 'trip' AND width > 5;
UPDATE id_sequences SET width = 3 WHERE seq_key LIKE 'req:%' AND width > 3;
