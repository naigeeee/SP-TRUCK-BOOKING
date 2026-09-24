-- Running sequence counters for Trip ID (SPT-*) and Request # (REQ-YYYYMMDD-*)
-- width starts at 7 (0000001..9999999); when a key exhausts its width the
-- counter wraps to the next wider zero-padded field (00000001, ...).
CREATE TABLE id_sequences (
    seq_key VARCHAR(64) NOT NULL PRIMARY KEY,
    width INT NOT NULL DEFAULT 7,
    next_value BIGINT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
