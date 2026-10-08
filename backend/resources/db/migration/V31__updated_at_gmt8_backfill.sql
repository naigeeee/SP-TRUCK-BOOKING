-- One-time GMT+8 backfill for updated_at.
--
-- The app used to write updated_at in UTC (nows() = datetime.now(timezone.utc))
-- while the database session's NOW()/ON UPDATE CURRENT_TIMESTAMP already ran in
-- GMT+8, so the stored values were mixed: rows stamped from application code sat
-- 8 hours behind the real local time shown in the Masterlist.
--
-- nows() and the database session are both GMT+8 from this release on, so the
-- stored value can be displayed as-is. This migration shifts every existing
-- row by +8 hours once to put them on the same clock.
--
-- Explicitly naming the column in SET bypasses ON UPDATE CURRENT_TIMESTAMP,
-- so this statement does not alter the timestamps it is fixing.
--
-- Rows that were already written by the database session (GMT+8) land 8 hours
-- ahead until the next update to that request rewrites them with nows(); at
-- most one such row is visible per recently-updated request and it self-heals.
UPDATE truck_requests
   SET updated_at = updated_at + INTERVAL 8 HOUR
 WHERE updated_at IS NOT NULL;
