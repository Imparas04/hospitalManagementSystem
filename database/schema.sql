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
    consultation_fee      DECIMAL(10,2) NOT NULL DEFAULT 500,   -- Rs. per completed appointment (Phase 6 billing)
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
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    ward_type           VARCHAR(20)  NOT NULL,   -- general|icu|isolation|maternity|pediatric
    gender_restriction  VARCHAR(10),             -- NULL = mixed, else 'male'/'female' (Phase 4: smart bed allocation)
    daily_charge        DECIMAL(10,2) NOT NULL DEFAULT 1000,   -- Rs. per day (Phase 6 billing)
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
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

-- ============================================================
-- Phase 4: triage_records (emergency vitals, priority, smart bed allocation link)
-- ============================================================
CREATE TABLE IF NOT EXISTS triage_records (
    id                          INT AUTO_INCREMENT PRIMARY KEY,
    patient_id                  INT          NOT NULL,
    blood_pressure_systolic     INT          NOT NULL,
    blood_pressure_diastolic    INT          NOT NULL,
    heart_rate                  INT          NOT NULL,
    oxygen_level                INT          NOT NULL,
    temperature                 FLOAT        NOT NULL,
    symptoms                    VARCHAR(500) NOT NULL,
    emergency_condition         VARCHAR(255),
    icu_required                BOOLEAN      NOT NULL DEFAULT FALSE,
    isolation_required          BOOLEAN      NOT NULL DEFAULT FALSE,
    priority_level               VARCHAR(10)  NOT NULL,  -- critical|high|medium|low (computed)
    priority_score               INT          NOT NULL,
    status                       VARCHAR(20)  NOT NULL DEFAULT 'waiting',  -- waiting|bed_assigned|in_treatment|resolved
    admission_id                 INT,
    recorded_by_id                INT         NOT NULL,
    recorded_at                   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_triage_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_triage_admission FOREIGN KEY (admission_id) REFERENCES admissions(id),
    CONSTRAINT fk_triage_recorded_by FOREIGN KEY (recorded_by_id) REFERENCES users(id),
    INDEX ix_triage_patient (patient_id),
    INDEX ix_triage_status (status)
) ENGINE=InnoDB;

-- ============================================================
-- Phase 5: laboratory (lab_tests, lab_orders, lab_results) and
--          pharmacy (medicines, medicine_stock, prescriptions, prescription_items)
-- ============================================================

-- ---------- lab_tests (master catalog: CBC, LFT, KFT, ...) ----------
CREATE TABLE IF NOT EXISTS lab_tests (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    code          VARCHAR(20)  NOT NULL,
    normal_range  VARCHAR(100),
    price         DECIMAL(10,2) NOT NULL DEFAULT 300,   -- Rs. per test (Phase 6 billing)
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_lab_tests_code UNIQUE (code)
) ENGINE=InnoDB;

-- ---------- lab_orders (a doctor prescribes a test for a patient) ----------
CREATE TABLE IF NOT EXISTS lab_orders (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    patient_id   INT          NOT NULL,
    doctor_id    INT          NOT NULL,
    lab_test_id  INT          NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'ordered',  -- ordered|sample_collected|processing|result_entered|reviewed
    notes        VARCHAR(500),
    ordered_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_lab_orders_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_lab_orders_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    CONSTRAINT fk_lab_orders_test FOREIGN KEY (lab_test_id) REFERENCES lab_tests(id),
    INDEX ix_lab_orders_patient (patient_id)
) ENGINE=InnoDB;

-- ---------- lab_results (one result per order) ----------
CREATE TABLE IF NOT EXISTS lab_results (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    lab_order_id    INT          NOT NULL,
    result_value    VARCHAR(500) NOT NULL,
    is_abnormal     BOOLEAN      NOT NULL DEFAULT FALSE,
    entered_by_id   INT          NOT NULL,
    entered_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewer_notes  VARCHAR(500),
    reviewed_by_id  INT,
    reviewed_at     DATETIME,
    CONSTRAINT uq_lab_results_order UNIQUE (lab_order_id),
    CONSTRAINT fk_lab_results_order FOREIGN KEY (lab_order_id) REFERENCES lab_orders(id),
    CONSTRAINT fk_lab_results_entered_by FOREIGN KEY (entered_by_id) REFERENCES users(id),
    CONSTRAINT fk_lab_results_reviewed_by FOREIGN KEY (reviewed_by_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------- medicines (master catalog, NOT stock) ----------
CREATE TABLE IF NOT EXISTS medicines (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    unit           VARCHAR(20)  NOT NULL,   -- tablet|syrup|injection|ointment|drops
    reorder_level  INT          NOT NULL DEFAULT 10,   -- total stock below this = low-stock alert
    unit_price     DECIMAL(10,2) NOT NULL DEFAULT 10,  -- Rs. per unit (Phase 6 billing)
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_medicines_name UNIQUE (name)
) ENGINE=InnoDB;

-- ---------- medicine_stock (one row per purchased batch) ----------
CREATE TABLE IF NOT EXISTS medicine_stock (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id         INT         NOT NULL,
    batch_number        VARCHAR(50) NOT NULL,
    expiry_date         DATE        NOT NULL,
    purchase_quantity   INT         NOT NULL,
    available_quantity  INT         NOT NULL,
    created_at          DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    CONSTRAINT uq_medicine_batch_number UNIQUE (medicine_id, batch_number),
    INDEX ix_stock_medicine (medicine_id),
    INDEX ix_stock_expiry (expiry_date)
) ENGINE=InnoDB;

-- ---------- prescriptions ----------
CREATE TABLE IF NOT EXISTS prescriptions (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    patient_id  INT         NOT NULL,
    doctor_id   INT         NOT NULL,
    notes       VARCHAR(500),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending|partially_issued|issued
    created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prescriptions_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_prescriptions_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    INDEX ix_prescriptions_patient (patient_id)
) ENGINE=InnoDB;

-- ---------- prescription_items ----------
CREATE TABLE IF NOT EXISTS prescription_items (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id      INT          NOT NULL,
    medicine_id          INT          NOT NULL,
    dosage               VARCHAR(100) NOT NULL,
    quantity_prescribed  INT          NOT NULL,
    quantity_issued      INT          NOT NULL DEFAULT 0,
    CONSTRAINT fk_presc_items_prescription FOREIGN KEY (prescription_id) REFERENCES prescriptions(id),
    CONSTRAINT fk_presc_items_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    INDEX ix_presc_items_prescription (prescription_id)
) ENGINE=InnoDB;

-- ============================================================
-- Phase 6: bills, bill_items, payments, discharge_summaries
-- (also: price columns added above on doctors, wards, lab_tests, medicines)
-- ============================================================

-- ---------- bills ----------
CREATE TABLE IF NOT EXISTS bills (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    bill_number       VARCHAR(20)   NOT NULL,                 -- e.g. B2026000001
    patient_id        INT           NOT NULL,
    subtotal          DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_percent  DECIMAL(5,2)  NOT NULL DEFAULT 0,
    discount_amount   DECIMAL(10,2) NOT NULL DEFAULT 0,
    tax_percent       DECIMAL(5,2)  NOT NULL DEFAULT 0,
    tax_amount        DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount      DECIMAL(10,2) NOT NULL DEFAULT 0,
    amount_paid       DECIMAL(10,2) NOT NULL DEFAULT 0,
    status            VARCHAR(20)   NOT NULL DEFAULT 'unpaid',  -- unpaid|partially_paid|paid
    created_by_id     INT           NOT NULL,
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_bills_number UNIQUE (bill_number),
    CONSTRAINT fk_bills_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_bills_created_by FOREIGN KEY (created_by_id) REFERENCES users(id),
    INDEX ix_bills_patient (patient_id),
    INDEX ix_bills_status (status)
) ENGINE=InnoDB;

-- ---------- bill_items (one line per charge) ----------
CREATE TABLE IF NOT EXISTS bill_items (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    bill_id      INT           NOT NULL,
    category     VARCHAR(20)   NOT NULL,        -- consultation|bed|laboratory|medicine|other
    description  VARCHAR(255)  NOT NULL,
    quantity     INT           NOT NULL DEFAULT 1,
    unit_price   DECIMAL(10,2) NOT NULL,        -- price at billing time (snapshot)
    amount       DECIMAL(10,2) NOT NULL,        -- quantity * unit_price
    source_type  VARCHAR(30),                   -- appointment|lab_order|admission|prescription_item
    source_id    INT,
    source_key   VARCHAR(50),                   -- e.g. 'appointment:5' - UNIQUE, so a service can never be billed twice
    CONSTRAINT uq_bill_items_source_key UNIQUE (source_key),
    CONSTRAINT fk_bill_items_bill FOREIGN KEY (bill_id) REFERENCES bills(id),
    INDEX ix_bill_items_bill (bill_id)
) ENGINE=InnoDB;

-- ---------- payments (partial payments + multiple methods; one receipt each) ----------
CREATE TABLE IF NOT EXISTS payments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    receipt_number  VARCHAR(20)   NOT NULL,     -- e.g. R2026000001
    bill_id         INT           NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    method          VARCHAR(20)   NOT NULL,     -- cash|card|upi|bank_transfer|insurance
    reference       VARCHAR(100),
    received_by_id  INT           NOT NULL,
    paid_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_payments_receipt UNIQUE (receipt_number),
    CONSTRAINT fk_payments_bill FOREIGN KEY (bill_id) REFERENCES bills(id),
    CONSTRAINT fk_payments_received_by FOREIGN KEY (received_by_id) REFERENCES users(id),
    INDEX ix_payments_bill (bill_id)
) ENGINE=InnoDB;

-- ---------- discharge_summaries (one per admission) ----------
CREATE TABLE IF NOT EXISTS discharge_summaries (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    admission_id         INT           NOT NULL,
    diagnosis            VARCHAR(500)  NOT NULL,
    treatment_summary    VARCHAR(2000) NOT NULL,
    doctor_instructions  VARCHAR(1000),
    follow_up_date       DATE,
    created_by_id        INT           NOT NULL,
    created_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_discharge_admission UNIQUE (admission_id),
    CONSTRAINT fk_discharge_admission FOREIGN KEY (admission_id) REFERENCES admissions(id),
    CONSTRAINT fk_discharge_created_by FOREIGN KEY (created_by_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- ============================================================
-- Phase 7: audit_logs, notifications, notification_reads
-- ============================================================

-- ---------- audit_logs (append-only: the API has no edit/delete for it) ----------
CREATE TABLE IF NOT EXISTS audit_logs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT,                          -- NULL for a failed login (nobody is logged in)
    username     VARCHAR(50),                  -- copied, so history stays right if the user is renamed
    role         VARCHAR(30),                  -- copied, so history stays right if the role changes
    action       VARCHAR(50)  NOT NULL,        -- e.g. patient.create, lab_order.result_entered
    entity_type  VARCHAR(30),                  -- e.g. Patient, Bill
    entity_id    INT,
    description  VARCHAR(500) NOT NULL,
    ip_address   VARCHAR(45),
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX ix_audit_user (user_id),
    INDEX ix_audit_action (action),
    INDEX ix_audit_created (created_at),
    INDEX ix_audit_entity (entity_type, entity_id)
) ENGINE=InnoDB;

-- ---------- notifications (to one user OR to everyone with a role) ----------
CREATE TABLE IF NOT EXISTS notifications (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    type            VARCHAR(30)  NOT NULL,     -- lab_result|low_stock|medicine_expiry|payment_pending|patient_discharge
    title           VARCHAR(150) NOT NULL,
    message         VARCHAR(500) NOT NULL,
    severity        VARCHAR(10)  NOT NULL DEFAULT 'info',   -- info|warning|critical
    target_role     VARCHAR(30),
    target_user_id  INT,
    entity_type     VARCHAR(30),
    entity_id       INT,
    dedupe_key      VARCHAR(60),               -- alerts only, e.g. 'low_stock:7' - UNIQUE, so an alert is never created twice
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME,                  -- set when the condition goes away (e.g. medicine restocked)
    CONSTRAINT uq_notifications_dedupe UNIQUE (dedupe_key),
    CONSTRAINT fk_notifications_user FOREIGN KEY (target_user_id) REFERENCES users(id),
    INDEX ix_notifications_role (target_role),
    INDEX ix_notifications_user (target_user_id),
    INDEX ix_notifications_created (created_at)
) ENGINE=InnoDB;

-- ---------- notification_reads (who has read what - per user, not shared) ----------
CREATE TABLE IF NOT EXISTS notification_reads (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    notification_id  INT      NOT NULL,
    user_id          INT      NOT NULL,
    read_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_notification_reader UNIQUE (notification_id, user_id),
    CONSTRAINT fk_reads_notification FOREIGN KEY (notification_id) REFERENCES notifications(id),
    CONSTRAINT fk_reads_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;
