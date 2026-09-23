-- Restore foul-trip drop_sequence / truck link from history so masterlist
-- keeps Trip ID, Drop # and Distance after Allocated -> Foul Trip.
UPDATE truck_requests tr
JOIN (
    SELECT h.truck_request_id, h.truck_id, h.drop_sequence
    FROM truck_request_history h
    WHERE h.status_id = 7
      AND h.archived_at = (
          SELECT MAX(h2.archived_at) FROM truck_request_history h2
          WHERE h2.truck_request_id = h.truck_request_id
      )
) h ON h.truck_request_id = tr.id
SET tr.drop_sequence = COALESCE(tr.drop_sequence, h.drop_sequence),
    tr.assigned_truck_id = COALESCE(tr.assigned_truck_id, h.truck_id)
WHERE tr.status_id = 7
  AND (tr.drop_sequence IS NULL OR tr.assigned_truck_id IS NULL);
