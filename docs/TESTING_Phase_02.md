# Testing - Phase 2

## Automated tests (pytest)
```bash
pytest -v
```
Expected: **62 passed** (31 from Phase 1 + 31 new). In-memory SQLite, your MySQL data is untouched.

New coverage (`tests/test_patients.py`):

| Area | Cases |
|---|---|
| Success | create, get, update, deactivate, search/filter, pagination, add/list medical history, add/list visits |
| Patient ID | generated, unique, increasing per year |
| Invalid input | missing fields, bad date/gender/phone/email/blood group, empty update body |
| RBAC | only receptionist/admin create; receptionist/doctor/nurse/admin read; lab/pharmacy/billing blocked; only receptionist/doctor update |
| Edge cases | emergency registration with minimal data sets `registration_pending`, deactivated patient drops out of default list, 404 for unknown patient/history target |

## Manual test on real MySQL
1. Server running from Phase 1 setup.
2. Import `postman/Hospital_Phase02.postman_collection.json`, run the 4 **Logins** requests first (each saves its token).
3. Run **Create patient** -> note the `patient_code` returned (e.g. `P2026000001`).
4. Run **List / search patients** -> confirm the patient appears.
5. Try **Create patient** with the *doctor* token manually (change the Authorization) -> expect `403`.
6. Run **Add medical history (doctor)** then **List medical history** (as nurse) -> confirm it appears.
7. Run **Deactivate patient**, then **List / search patients** again -> patient should be missing (add `?is_active=false` to see it).

| # | Test | Expected |
|---|---|---|
| 1 | Create patient as receptionist | 201, patient_code returned |
| 2 | Create patient as pharmacist | 403 |
| 3 | Create patient missing phone | 400, `errors.phone` |
| 4 | Read patients as lab_technician | 403 |
| 5 | Update patient as nurse | 403 |
| 6 | Update patient as doctor | 200 |
| 7 | Get unknown patient id | 404 |
| 8 | Emergency registration | `registration_pending: true` |
