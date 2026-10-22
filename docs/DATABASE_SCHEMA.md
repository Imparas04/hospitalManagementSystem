# Database Schema Overview

This is a high-level map of model modules under `backend/app/models/`, not an exhaustive field-level schema. For exact columns, constraints, nullability, and relationships, read the model definitions.

| Area | Model module | Purpose |
|---|---|---|
| Patients | `patient.py` | Patient profiles, medical history, visits |
| Doctors/departments | `doctor.py` | Doctor profiles, departments, schedules |
| Appointments | `appointment.py` | Appointments linked to patients and doctors |
| Beds | `bed.py` | Bed allocation with patient/doctor references |
| Billing | `billing.py` | Billing records and patient association |
| Pharmacy | `pharmacy.py` | Medicines, batches, prescriptions, prescription items |
| Emergency/triage | `triage.py` | Triage assessments and emergency workflow |
| Audit | `audit.py` | Audit trail records |
| Roles | `role.py` | Role/access-control support |
| Laboratory | `lab.py` | Lab records with patient/doctor associations |

## Relationships confirmed in model source
- Appointments reference patients and doctors.
- Bed records include patient and doctor references.
- Billing records reference patients.
- Lab and triage records reference patients; lab records also reference doctors.
- Doctors belong to departments and can have schedules.
- Patient records can have related medical-history and visit records.
- Pharmacy models include prescription and stock-batch concepts.

## Schema maintenance
Review foreign keys and relationships when models change. Use the project's established migration/database workflow, test changes against a development database, and never publish real patient data or database dumps.
