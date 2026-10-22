# API Documentation - Phase 3 (Doctor, Appointment, Admission)

Adds to Phases 1-2. Same conventions: JSON body, `Authorization: Bearer <token>`, same success/error shape and status codes.

**Permissions for this phase** (admin always has access):

| Permission | Roles |
|---|---|
| `departments:read` / `doctors:read` | receptionist, doctor, nurse |
| departments/doctors create & update | **admin only** |
| `appointments:read` | receptionist, doctor, nurse |
| `appointments:create` | receptionist |
| `appointments:update` | receptionist, doctor |
| `wards:read` / `beds:read` | receptionist, doctor, nurse |
| `beds:update` | nurse |
| `admissions:read` | receptionist, doctor, nurse |
| `admissions:create` | receptionist |
| `admissions:update` (discharge) | receptionist, nurse |
| wards/beds create | **admin only** |

---

## Departments
`POST /api/departments` (admin) `{"name": "Cardiology", "description": "..."}` -> `201`
`GET /api/departments?is_active=true` -> array
`PUT /api/departments/<id>` (admin) -> partial update (`name`, `description`, `is_active`)

## Doctors
A "doctor profile" links an **existing user** (whose account role is `doctor`, created in Phase 1's `/api/users`) to a department and specialization.

`POST /api/doctors` (admin)
```json
{"user_id": 3, "department_id": 1, "specialization": "Cardiologist", "is_on_emergency_duty": false}
```
Errors `400` if the user doesn't exist, isn't role `doctor`, or already has a doctor profile; if the department doesn't exist.

`GET /api/doctors?department_id=&specialization=&emergency_duty=true&q=&is_active=`
`GET /api/doctors/<id>` -> includes `schedules: [...]`
`PUT /api/doctors/<id>` (admin) -> partial update

### Doctor schedule (weekly recurring availability)
`POST /api/doctors/<id>/schedule` (admin)
```json
{"day_of_week": 0, "start_time": "09:00", "end_time": "13:00", "slot_minutes": 15}
```
`day_of_week`: `0` = Monday ... `6` = Sunday. This creates one weekly recurring block; add more rows for more days/shifts.

`GET /api/doctors/<id>/schedule` -> array of blocks

### Doctor availability (computed)
`GET /api/doctors/<id>/availability?date=2026-10-12` - Auth: **appointments:read**

Returns every free `HH:MM` slot for that specific date (weekday's schedule blocks, minus already-booked appointments). The frontend should call this before showing a booking form.
```json
{"date": "2026-10-12", "doctor_id": 1, "slots": ["09:00", "09:15", "09:30"]}
```

---

## Appointments

### Book
`POST /api/appointments` - Auth: **appointments:create**
```json
{"patient_id": 1, "doctor_id": 1, "appointment_date": "2026-10-12",
 "appointment_time": "09:00", "reason": "Chest pain", "notes": "optional"}
```
**Behavior:** if the slot is free, status is `scheduled` (`201`). If taken, the appointment is created as `waitlisted` instead of failing (`201`, message mentions "waiting list") - this is the "waiting-list management" feature from the requirement doc. Send `"allow_waitlist": false` to instead get a `409` when the slot is taken (useful if your frontend wants to show "pick another slot" immediately).

### List / filter
`GET /api/appointments?doctor_id=&patient_id=&department_id=&status=&date=&page=&per_page=`

### Waiting list
`GET /api/appointments/waiting-list?doctor_id=&department_id=` -> array of `waitlisted` appointments

### Get one
`GET /api/appointments/<id>`

### Reschedule / edit
`PUT /api/appointments/<id>` - Auth: **appointments:update**
Send any of `appointment_date`, `appointment_time`, `doctor_id`, `reason`, `notes`. Re-checks the new slot; `409` if taken. Blocked (`400`) on `cancelled`/`completed` appointments.

### Status changes
`POST /api/appointments/<id>/cancel` -> status `cancelled` (frees the slot for others)
`POST /api/appointments/<id>/complete` -> status `completed` (only from `scheduled`)
`POST /api/appointments/<id>/no-show` -> status `no_show` (only from `scheduled`)
`POST /api/appointments/<id>/promote` -> tries to move a `waitlisted` appointment into its requested slot (call this after a cancellation); `409` if the slot is still taken.

---

## Wards & Beds
`POST /api/wards` (admin) `{"name": "General Ward A", "ward_type": "general"}` - `ward_type`: `general`|`icu`|`isolation`|`maternity`|`pediatric`
`GET /api/wards` -> each ward includes `total_beds` and `available_beds`
`POST /api/wards/<id>/beds` (admin) `{"bed_number": "A-101", "bed_type": "general"}` - `bed_type`: `general`|`icu`|`isolation`
`GET /api/beds?ward_id=&status=&bed_type=`
`PUT /api/beds/<id>` - Auth: **beds:update** (nurse/admin) - `{"status": "maintenance"}`. You **cannot** free an `occupied` bed this way (`400`) - discharge the patient instead, which frees it automatically.

## Admissions
`POST /api/admissions` - Auth: **admissions:create**
```json
{"patient_id": 1, "bed_id": 5, "doctor_id": 1, "reason": "Observation"}
```
`409` if the bed isn't `available`. On success the bed is marked `occupied` automatically.

> Bed selection here is manual (reception/nursing pick a specific `bed_id`). **Automatic smart bed allocation** (matching ward type, bed type, patient gender, ICU/isolation needs and emergency priority) is built in **Phase 4** on top of this same `admissions`/`beds` foundation - the API shape will stay compatible.

`GET /api/admissions?patient_id=&status=&ward_id=&page=&per_page=`
`GET /api/admissions/<id>`
`POST /api/admissions/<id>/discharge` - Auth: **admissions:update** - sets `discharge_date`, frees the bed automatically. `400` if already discharged.

---

## Typical booking flow (frontend)
1. `GET /api/departments` -> `GET /api/doctors?department_id=...` -> pick a doctor
2. `GET /api/doctors/<id>/availability?date=...` -> show free slots
3. `POST /api/appointments` with the chosen slot

Postman: `postman/Hospital_Phase03.postman_collection.json`.
