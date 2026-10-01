-- Seed data (Phase 1): the 7 roles. Safe to run more than once.
-- The first ADMIN user is created with:  flask create-admin
-- (so that no password is ever written in a file)
USE hospital_db;

INSERT IGNORE INTO roles (name, description) VALUES
 ('admin',          'Full system access'),
 ('receptionist',   'Patients, appointments and admissions'),
 ('doctor',         'Patients, appointments, prescriptions and lab reports'),
 ('nurse',          'Patient care, bed allocation and vital signs'),
 ('lab_technician', 'Lab tests, samples and results'),
 ('pharmacist',     'Prescriptions and medicine inventory'),
 ('billing_staff',  'Bills, payments and receipts');
