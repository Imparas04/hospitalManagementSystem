# Testing - Phase 3

## Automated tests (pytest)
```bash
pytest -v
```
Expected: **127 passed** (62 from Phases 1-2 + 65 new). In-memory SQLite, your MySQL data is untouched.

New coverage:

| File | Area |
|---|---|
| `test_departments_doctors.py` | department CRUD + RBAC, doctor profile creation (must link a `doctor`-role user, rejects duplicates/unknown refs), schedule validation, computed availability |
| `test_appointments.py` | booking into a free slot, **double-booking auto-waitlists**, `allow_waitlist:false` -> 409, booking with no schedule at all -> waitlisted, reschedule (success + conflict), cancel/complete/no-show transitions, **cancel frees the slot for rebooking**, waiting list + promote (including promote failing if still taken), RBAC per role |
| `test_admissions.py` | ward/bed CRUD + RBAC, duplicate bed number rejected, admit occupies the bed, **double-admit to the same bed -> 409**, discharge frees the bed + blocks double-discharge, filters/pagination |

Key edge case specifically tested: a waitlisted appointment being promoted does **not** block itself as "already booked" (a self-conflict bug caught and fixed during this phase - see `exclude_appointment_id` in `app/services/doctor_service.py`).

## Manual test on real MySQL
1. Import `postman/Hospital_Phase03.postman_collection.json`.
2. Run the 4 **Logins** requests (each saves its token; the doctor login also saves `doctor_user_id`).
3. Run everything in **Departments & Doctors**, then **Patients**, then **Appointments**, then **Wards, Beds & Admissions**, top to bottom - each request saves the id the next one needs (`department_id`, `doctor_id`, `patient_id`, `appointment_id`, `ward_id`, `bed_id`, `admission_id`).
4. Confirm "Book same slot again" returns `201` with `status: waitlisted`, not an error.
5. Confirm "Discharge patient" frees the bed - call **List beds** again afterward and check `status: available`.

| # | Test | Expected |
|---|---|---|
| 1 | Create doctor profile with a non-doctor user | 400 |
| 2 | Book appointment in a free slot | 201, `scheduled` |
| 3 | Book the same slot again | 201, `waitlisted` (not an error) |
| 4 | Book with `allow_waitlist: false` on a taken slot | 409 |
| 5 | Admit to an already-occupied bed | 409 |
| 6 | Free an occupied bed via `PUT /beds/<id>` directly | 400 (must discharge) |
| 7 | Pharmacist reads `/api/appointments` | 403 |
