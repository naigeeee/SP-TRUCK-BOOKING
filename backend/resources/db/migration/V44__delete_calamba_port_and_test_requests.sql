-- V44: one-off clean-up requested by the master admin: hard-delete the port "Calamba"
--      (code 'Calamba', id 2000088 in production) and the three Cancelled test requests
--      that use it (REQ-20261124-002, REQ-20261123-005, REQ-20261123-004), with every row
--      that belongs to those requests.
--
-- Every statement matches the exact request ids + request numbers + Cancelled status +
-- the Calamba port at once, so in any other database (e.g. dev) it finds nothing to
-- delete. The port itself is deleted only if nothing references it any more, so this
-- can never fail on a foreign key (a failed migration would block every later deploy).

-- Rows without a foreign key to truck_requests (would otherwise be left orphaned).
DELETE FROM scan_unload_items
WHERE request_id IN (
    SELECT id FROM (
        SELECT tr.id FROM truck_requests tr
        WHERE tr.id IN (22, 23, 37)
          AND tr.request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
          AND tr.status_id = 5
          AND (tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
          AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba')
    ) x
);

DELETE FROM scan_pickup_items
WHERE request_id IN (
    SELECT id FROM (
        SELECT tr.id FROM truck_requests tr
        WHERE tr.id IN (22, 23, 37)
          AND tr.request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
          AND tr.status_id = 5
          AND (tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
          AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba')
    ) x
);

DELETE FROM request_manifests
WHERE truck_request_id IN (
    SELECT id FROM (
        SELECT tr.id FROM truck_requests tr
        WHERE tr.id IN (22, 23, 37)
          AND tr.request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
          AND tr.status_id = 5
          AND (tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
          AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba')
    ) x
);

DELETE FROM truck_request_history
WHERE truck_request_id IN (
    SELECT id FROM (
        SELECT tr.id FROM truck_requests tr
        WHERE tr.id IN (22, 23, 37)
          AND tr.request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
          AND tr.status_id = 5
          AND (tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
          AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba')
    ) x
);

DELETE FROM drive_backup_files
WHERE request_id IN (
    SELECT id FROM (
        SELECT tr.id FROM truck_requests tr
        WHERE tr.id IN (22, 23, 37)
          AND tr.request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
          AND tr.status_id = 5
          AND (tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
          AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba')
    ) x
);

DELETE FROM drive_backup_folders
WHERE request_id IN (
    SELECT id FROM (
        SELECT tr.id FROM truck_requests tr
        WHERE tr.id IN (22, 23, 37)
          AND tr.request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
          AND tr.status_id = 5
          AND (tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
          AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba')
    ) x
);

-- The three requests. Their attachments and pending_allocations rows go with them
-- (ON DELETE CASCADE).
DELETE FROM truck_requests
WHERE id IN (22, 23, 37)
  AND request_number IN ('REQ-20261124-002', 'REQ-20261123-005', 'REQ-20261123-004')
  AND status_id = 5
  AND (origin_port_id = 2000088 OR destination_port_id = 2000088)
  AND EXISTS (SELECT 1 FROM ports p WHERE p.id = 2000088 AND p.code = 'Calamba');

-- The port, only when nothing points at it any more.
DELETE FROM ports
WHERE id = 2000088
  AND code = 'Calamba'
  AND NOT EXISTS (SELECT 1 FROM truck_requests tr WHERE tr.origin_port_id = 2000088 OR tr.destination_port_id = 2000088)
  AND NOT EXISTS (SELECT 1 FROM truck_request_history h WHERE h.origin_port_id = 2000088 OR h.destination_port_id = 2000088)
  AND NOT EXISTS (SELECT 1 FROM vendor_rates vr WHERE vr.origin_port_id = 2000088 OR vr.destination_port_id = 2000088
                                                  OR CAST(vr.destination_drops AS CHAR) LIKE '%2000088%');
