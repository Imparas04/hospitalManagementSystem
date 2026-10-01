-- ============================================================
-- Smart Hospital Management System - DATABASE SCHEMA
-- Phase 1: roles, users
-- Later phases will ADD tables to this file (nothing here gets removed).
-- Run:  mysql -u <user> -p < database/schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS hospital_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hospital_db;

-- ---------- roles ----------
CREATE TABLE IF NOT EXISTS roles (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(30)  NOT NULL,
    description VARCHAR(255),
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_roles_name UNIQUE (name)
) ENGINE=InnoDB;

-- ---------- users (staff accounts) ----------
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL,
    email         VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,          -- hashed, never plain text
    full_name     VARCHAR(100) NOT NULL,
    phone         VARCHAR(20),
    role_id       INT          NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login_at DATETIME,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email),
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(id),
    INDEX ix_users_role_id (role_id)
) ENGINE=InnoDB;

-- ============================================================
-- Phase 2: patients, medical_history, visit_history
-- ============================================================

-- ---------- patients ----------
CREATE TABLE IF NOT EXISTS patients (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    patient_code            VARCHAR(20)  NOT NULL,          -- e.g. P2026000001
    full_name               VARCHAR(100) NOT NULL,
    date_of_birth           DATE         NOT NULL,
    gender                  VARCHAR(10)  NOT NULL,           -- male | female | other
    blood_group             VARCHAR(10)  NOT NULL DEFAULT 'unknown',
    phone                   VARCHAR(20)  NOT NULL,
    email                   VARCHAR(120),
    address                 VARCHAR(255),
    emergency_contact_name  VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    is_emergency_registration BOOLEAN    NOT NULL DEFAULT FALSE,
    registration_pending    BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by_id           INT          NOT NULL,
    created_at               DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_patients_code UNIQUE (patient_code),
    CONSTRAINT fk_patients_created_by FOREIGN KEY (created_by_id) REFERENCES users(id),
    INDEX ix_patients_code (patient_code),
    INDEX ix_patients_full_name (full_name),
    INDEX ix_patients_phone (phone)
) ENGINE=InnoDB;

-- ---------- medical_history ----------
CREATE TABLE IF NOT EXISTS medical_history (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT          NOT NULL,
    condition_type  VARCHAR(30)  NOT NULL,   -- allergy | chronic_condition | surgery | note
    description     VARCHAR(500) NOT NULL,
    recorded_by_id  INT          NOT NULL,
    recorded_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mh_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_mh_recorded_by FOREIGN KEY (recorded_by_id) REFERENCES users(id),
    INDEX ix_mh_patient_id (patient_id)
) ENGINE=InnoDB;

-- ---------- visit_history ----------
CREATE TABLE IF NOT EXISTS visit_history (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT          NOT NULL,
    visit_date      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    visit_type      VARCHAR(20)  NOT NULL,   -- opd | emergency | follow_up
    reason          VARCHAR(255) NOT NULL,
    notes           VARCHAR(500),
    recorded_by_id  INT          NOT NULL,
    CONSTRAINT fk_vh_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_vh_recorded_by FOREIGN KEY (recorded_by_id) REFERENCES users(id),
    INDEX ix_vh_patient_id (patient_id)
) ENGINE=InnoDB;
