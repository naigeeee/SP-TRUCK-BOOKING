-- V3__complete_rebuild_with_all_columns.sql
-- Complete wipe and rebuild: drops all tables and recreates with full schema

-- =============================================
-- DROP ALL TABLES (reverse FK order)
-- =============================================
DROP TABLE IF EXISTS truck_request_history;
DROP TABLE IF EXISTS pending_allocations;
DROP TABLE IF EXISTS truck_request_attachments;
DROP TABLE IF EXISTS vendor_evaluations;
DROP TABLE IF EXISTS truck_requests;
DROP TABLE IF EXISTS vendor_rates;
DROP TABLE IF EXISTS trucks;
DROP TABLE IF EXISTS truck_type_capacities;
DROP TABLE IF EXISTS truck_types;
DROP TABLE IF EXISTS truck_statuses;
DROP TABLE IF EXISTS packaging_types;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS ports;
DROP TABLE IF EXISTS users;

-- =============================================
-- RECREATE ALL TABLES (forward FK order)
-- =============================================

-- Users table
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    role ENUM('master_admin', 'admin', 'normal_user') NOT NULL DEFAULT 'normal_user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Ports table
CREATE TABLE ports (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    location VARCHAR(255),
    latitude DECIMAL(10, 7) NULL,
    longitude DECIMAL(10, 7) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts table
CREATE TABLE accounts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Departments table
CREATE TABLE departments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vendors table
CREATE TABLE vendors (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Packaging types table
CREATE TABLE packaging_types (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Truck request statuses table
CREATE TABLE truck_statuses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(20) DEFAULT '#6B7280',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Truck types table
CREATE TABLE truck_types (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    max_capacity_kg DECIMAL(10,2),
    max_capacity_cbm DECIMAL(10,2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Truck type capacities per packaging type
CREATE TABLE truck_type_capacities (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_type_id BIGINT NOT NULL,
    packaging_type_id BIGINT NOT NULL,
    max_quantity INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (truck_type_id) REFERENCES truck_types(id) ON DELETE CASCADE,
    FOREIGN KEY (packaging_type_id) REFERENCES packaging_types(id) ON DELETE CASCADE,
    UNIQUE KEY uk_truck_packaging (truck_type_id, packaging_type_id)
);

-- Trucks (fleet) table
CREATE TABLE trucks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(50) NOT NULL UNIQUE,
    truck_type_id BIGINT NOT NULL,
    vendor_id BIGINT,
    driver_name VARCHAR(255),
    driver_phone VARCHAR(50),
    helper_name VARCHAR(255) NULL,
    status ENUM('available', 'assigned', 'maintenance') NOT NULL DEFAULT 'available',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (truck_type_id) REFERENCES truck_types(id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
);

-- Main truck requests table (with drop_sequence column)
CREATE TABLE truck_requests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_number VARCHAR(50) NOT NULL UNIQUE,
    requestor_email VARCHAR(255) NOT NULL,
    requestor_name VARCHAR(255) NOT NULL,
    account_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    origin_port_id BIGINT NOT NULL,
    destination_port_id BIGINT NOT NULL,
    pickup_datetime DATETIME,
    call_datetime DATETIME,
    customs_cleared_datetime DATETIME,
    booking_date DATE,
    delivery_datetime DATETIME,
    truck_type_id BIGINT NOT NULL,
    packaging_type_id BIGINT,
    quantity INT DEFAULT 0,
    weight_kg DECIMAL(10,2) DEFAULT 0,
    volume_cbm DECIMAL(10,2) DEFAULT 0,
    special_instructions TEXT,
    status_id BIGINT NOT NULL,
    assigned_truck_id BIGINT,
    drop_sequence INT NULL,
    estimated_cost DECIMAL(12,2) DEFAULT 0,
    actual_cost DECIMAL(12,2) DEFAULT 0,
    updated_by VARCHAR(255),
    trip_date DATETIME,
    arrived_pickup_datetime DATETIME,
    start_loading_datetime DATETIME,
    end_loading_datetime DATETIME,
    arrived_dest_datetime DATETIME,
    start_unloading_datetime DATETIME,
    end_unloading_datetime DATETIME,
    foul_trip_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (origin_port_id) REFERENCES ports(id),
    FOREIGN KEY (destination_port_id) REFERENCES ports(id),
    FOREIGN KEY (truck_type_id) REFERENCES truck_types(id),
    FOREIGN KEY (packaging_type_id) REFERENCES packaging_types(id),
    FOREIGN KEY (status_id) REFERENCES truck_statuses(id),
    FOREIGN KEY (assigned_truck_id) REFERENCES trucks(id)
);

-- Attachments table
CREATE TABLE truck_request_attachments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_request_id BIGINT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INT NOT NULL,
    file_type VARCHAR(100),
    storage_path VARCHAR(500) NOT NULL,
    uploaded_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (truck_request_id) REFERENCES truck_requests(id) ON DELETE CASCADE
);

-- Vendor rates table (with vendor_id, default_rate, destination_drops)
CREATE TABLE vendor_rates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    vendor_name VARCHAR(255) NOT NULL,
    vendor_id BIGINT NULL,
    truck_type_id BIGINT NOT NULL,
    origin_port_id BIGINT NOT NULL,
    destination_port_id BIGINT NOT NULL,
    rate_per_trip DECIMAL(12,2) DEFAULT 0,
    default_rate DECIMAL(12,2) DEFAULT 0,
    destination_drops JSON NULL,
    rate_per_kg DECIMAL(10,2) DEFAULT 0,
    rate_per_cbm DECIMAL(10,2) DEFAULT 0,
    effective_date DATE NOT NULL,
    expiry_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (truck_type_id) REFERENCES truck_types(id),
    FOREIGN KEY (origin_port_id) REFERENCES ports(id),
    FOREIGN KEY (destination_port_id) REFERENCES ports(id)
);

-- Vendor evaluations table
CREATE TABLE vendor_evaluations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    vendor_name VARCHAR(255) NOT NULL,
    evaluation_period VARCHAR(50) NOT NULL,
    period_type ENUM('weekly', 'monthly') NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_trips INT DEFAULT 0,
    on_time_deliveries INT DEFAULT 0,
    on_time_percentage DECIMAL(5,2) DEFAULT 0,
    average_rating DECIMAL(3,2) DEFAULT 0,
    total_cost DECIMAL(12,2) DEFAULT 0,
    notes TEXT,
    evaluated_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pending allocations table
CREATE TABLE pending_allocations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_request_id BIGINT NOT NULL,
    suggested_truck_id BIGINT,
    suggestion_reason TEXT,
    is_accepted BOOLEAN DEFAULT NULL,
    allocated_by VARCHAR(255),
    allocated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (truck_request_id) REFERENCES truck_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (suggested_truck_id) REFERENCES trucks(id)
);

-- Truck request history table (archive)
CREATE TABLE truck_request_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id BIGINT NOT NULL,
    truck_request_id BIGINT NOT NULL,
    request_number VARCHAR(50) NOT NULL,
    requestor_name VARCHAR(255) NOT NULL,
    requestor_email VARCHAR(255) NOT NULL,
    origin_port_id BIGINT NOT NULL,
    destination_port_id BIGINT NOT NULL,
    truck_type_id BIGINT NOT NULL,
    quantity INT DEFAULT 0,
    weight_kg DECIMAL(10,2) DEFAULT 0,
    volume_cbm DECIMAL(10,2) DEFAULT 0,
    status_id BIGINT NOT NULL,
    pickup_datetime DATETIME,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_by VARCHAR(255)
);

-- =============================================
-- SEED DATA
-- =============================================

-- Seed default departments
INSERT INTO departments (name, code) VALUES
('PHCC', 'PHCC'),
('PDFF', 'PDFF'),
('PDFF Provincial', 'PDFF Provincial'),
('3PL XDOC', '3PL XDOC');

-- Seed default truck statuses
INSERT INTO truck_statuses (name, code, color) VALUES
('Pending', 'pending', '#F59E0B'),
('Allocated', 'allocated', '#3B82F6'),
('In Transit', 'in_transit', '#8B5CF6'),
('Delivered', 'delivered', '#10B981'),
('Cancelled', 'cancelled', '#EF4444'),
('On Hold', 'on_hold', '#6B7280'),
('Foul Trip', 'foul_trip', '#DC2626');

-- Seed default master admin
INSERT INTO users (email, name, role) VALUES
('nigel.ng@ninjavan.co', 'Nigel Ng', 'master_admin');
