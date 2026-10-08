-- One Excel manifest file per truck request, with the bag/carton/gunny/sack IDs
-- already extracted from its key column so the CSV download can be served fast.
CREATE TABLE request_manifests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_request_id BIGINT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    storage_path VARCHAR(500) NULL,
    id_count INT NOT NULL DEFAULT 0,
    ids_json LONGTEXT NULL,
    uploaded_by VARCHAR(255) NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_request_manifest (truck_request_id)
);
