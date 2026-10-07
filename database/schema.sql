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

-- ============================================================
-- Phase 3: departments, doctors, doctor_schedules, appointments,
--          wards, beds, admissions
-- ============================================================

-- ---------- departments ----------
CREATE TABLE IF NOT EXISTS departments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_departments_name UNIQUE (name)
) ENGINE=InnoDB;

-- ---------- doctors (extra profile for a user whose role = 'doctor') ----------
CREATE TABLE IF NOT EXISTS doctors (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    user_id               INT          NOT NULL,
    department_id         INT          NOT NULL,
    specialization        VARCHAR(100) NOT NULL,
    is_on_emergency_duty  BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_doctors_user UNIQUE (user_id),
    CONSTRAINT fk_doctors_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_doctors_department FOREIGN KEY (department_id) REFERENCES departments(id),
    INDEX ix_doctors_department (department_id)
) ENGINE=InnoDB;

-- ---------- doctor_schedules (weekly recurring availability blocks) ----------
CREATE TABLE IF NOT EXISTS doctor_schedules (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id    INT      NOT NULL,
    day_of_week  INT      NOT NULL,   -- 0 = Monday ... 6 = Sunday
    start_time   TIME     NOT NULL,
    end_time     TIME     NOT NULL,
    slot_minutes INT      NOT NULL DEFAULT 15,
    CONSTRAINT fk_schedule_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    INDEX ix_schedule_doctor (doctor_id)
) ENGINE=InnoDB;

-- ---------- appointments ----------
CREATE TABLE IF NOT EXISTS appointments (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    patient_id        INT          NOT NULL,
    doctor_id         INT          NOT NULL,
    department_id     INT          NOT NULL,
    appointment_date  DATE         NOT NULL,
    appointment_time  TIME         NOT NULL,
    duration_minutes  INT          NOT NULL DEFAULT 15,
    status            VARCHAR(20)  NOT NULL DEFAULT 'scheduled',  -- scheduled|waitlisted|completed|cancelled|no_show
    reason            VARCHAR(255) NOT NULL,
    notes             VARCHAR(500),
    created_by_id     INT          NOT NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_appt_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    CONSTRAINT fk_appt_department FOREIGN KEY (department_id) REFERENCES departments(id),
    CONSTRAINT fk_appt_created_by FOREIGN KEY (created_by_id) REFERENCES users(id),
    INDEX ix_appt_patient (patient_id),
    INDEX ix_appt_doctor (doctor_id),
    INDEX ix_appt_date (appointment_date)
) ENGINE=InnoDB;

-- ---------- wards ----------
CREATE TABLE IF NOT EXISTS wards (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    ward_type  VARCHAR(20)  NOT NULL,   -- general|icu|isolation|maternity|pediatric
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_wards_name UNIQUE (name)
) ENGINE=InnoDB;

-- ---------- beds ----------
CREATE TABLE IF NOT EXISTS beds (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    ward_id    INT         NOT NULL,
    bed_number VARCHAR(20) NOT NULL,
    bed_type   VARCHAR(20) NOT NULL,   -- general|icu|isolation
    status     VARCHAR(20) NOT NULL DEFAULT 'available',  -- available|occupied|maintenance
    CONSTRAINT fk_beds_ward FOREIGN KEY (ward_id) REFERENCES wards(id),
    CONSTRAINT uq_ward_bed_number UNIQUE (ward_id, bed_number),
    INDEX ix_beds_ward (ward_id)
) ENGINE=InnoDB;

-- ---------- admissions ----------
CREATE TABLE IF NOT EXISTS admissions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT          NOT NULL,
    bed_id          INT          NOT NULL,
    doctor_id       INT          NOT NULL,
    reason          VARCHAR(255) NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'admitted',  -- admitted|discharged
    admission_date  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discharge_date  DATETIME,
    admitted_by_id  INT          NOT NULL,
    CONSTRAINT fk_admission_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_admission_bed FOREIGN KEY (bed_id) REFERENCES beds(id),
    CONSTRAINT fk_admission_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    CONSTRAINT fk_admission_admitted_by FOREIGN KEY (admitted_by_id) REFERENCES users(id),
    INDEX ix_admission_patient (patient_id),
    INDEX ix_admission_bed (bed_id)
) ENGINE=InnoDB;
