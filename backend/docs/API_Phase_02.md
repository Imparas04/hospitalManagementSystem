# API Documentation - Phase 2 (Patient Management)

Adds to Phase 1. Same conventions apply: JSON body, `Authorization: Bearer <token>`, same success/error shape, same status codes.

**Permissions for this phase** (admin can always do everything):

| Permission | Roles |
|---|---|
| `patients:read` | receptionist, doctor, nurse |
| `patients:create` | receptionist |
| `patients:update` | receptionist, doctor |

---

## 1. Register a patient
`POST /api/patients` - Auth: **patients:create**

Body:
```json
{
  "full_name": "Ramesh Kulkarni",
  "date_of_birth": "1990-05-15",
  "gender": "male",
  "blood_group": "B+",
  "phone": "+919876543210",
  "email": "ramesh@test.com",
  "address": "123 MG Road, Pune",
  "emergency_contact_name": "Sita Kulkarni",
  "emergency_contact_phone": "+919876543211",
  "is_emergency_registration": false
}
```
Required: `full_name`, `date_of_birth` (`YYYY-MM-DD`), `gender` (`male`|`female`|`other`), `phone`.
Optional: `blood_group` (`A+ A- B+ B- AB+ AB- O+ O- unknown`, default `unknown`), `email`, `address`, `emergency_contact_name`, `emergency_contact_phone`, `is_emergency_registration` (boolean, default `false`).

`patient_code` is generated automatically (`P<year><6-digit-sequence>`, e.g. `P2026000001`) - never send it yourself.

**Emergency registration:** when `is_emergency_registration` is `true`, the patient is created with `registration_pending: true` so receptionist knows to complete the file later (just `PUT` the missing fields and `{"registration_pending": false}` once done). You can still fill in placeholder values (e.g. `"full_name": "Unknown Male"`) if the patient is unconscious/unidentified.

Response `201`: the full patient object including `id`, `patient_code`, `age` (computed), `registration_pending`, `is_active`, timestamps.
Errors: `400` (field-level), `401`, `403`.

---

## 2. List / search patients
`GET /api/patients` - Auth: **patients:read**

Query params (all optional):

| Param | Meaning |
|---|---|
| `q` | search name, patient code or phone |
| `gender` | `male` \| `female` \| `other` |
| `blood_group` | e.g. `O+` (URL-encode `+` as `%2B`) |
| `emergency` | `true` -> only emergency registrations |
| `min_age`, `max_age` | whole numbers |
| `is_active` | `true` (default) \| `false` |
| `page`, `per_page` | default `1` / `10`, max `per_page` 100 |

Response `200`: same paginated shape as `/api/users` (`items`, `page`, `per_page`, `total`, `pages`).
Errors: `400` (bad page/age values), `401`, `403`.

---

## 3. Get one patient
`GET /api/patients/<id>?include_history=true` - Auth: **patients:read**

`include_history=true` adds `medical_history` and `visits` arrays to the response (otherwise omitted, to keep the normal response light).
Errors: `401`, `403`, `404`.

---

## 4. Update patient
`PUT /api/patients/<id>` - Auth: **patients:update**

Send only the fields to change (`full_name`, `date_of_birth`, `gender`, `blood_group`, `phone`, `email`, `address`, `emergency_contact_name`, `emergency_contact_phone`, `registration_pending`).
Errors: `400` (empty body / invalid values), `401`, `403`, `404`.

## 5. Deactivate patient (soft delete)
`DELETE /api/patients/<id>` - Auth: **patients:update**

Record is kept (medical/legal history must not disappear); `is_active` becomes `false` and it drops out of the default list. Re-activate with `PUT` + `{"is_active": true}` is **not** supported in Phase 2 — ask an admin if that's needed (can be added if your viva needs it).
Errors: `401`, `403`, `404`.

---

## 6. Medical history
`POST /api/patients/<id>/medical-history` - Auth: **patients:update**
```json
{"condition_type": "allergy", "description": "Penicillin allergy"}
```
`condition_type`: `allergy` | `chronic_condition` | `surgery` | `note`. Response `201`.

`GET /api/patients/<id>/medical-history` - Auth: **patients:read** -> array of entries, newest first.

## 7. Visit history
`POST /api/patients/<id>/visits` - Auth: **patients:update**
```json
{"visit_type": "opd", "reason": "Fever checkup", "notes": "Prescribed paracetamol"}
```
`visit_type`: `opd` | `emergency` | `follow_up`. `notes` optional. Response `201`.

`GET /api/patients/<id>/visits` - Auth: **patients:read** -> array of visits, newest first.

> Visits are a standalone log in Phase 2. From Phase 3 onward, real appointments/admissions will create these automatically — the shape of this API will not change, so the frontend built now keeps working.

---

## Sample JS (frontend)
```js
const token = localStorage.getItem("token");
const res = await fetch("http://localhost:5000/api/patients?q=Ramesh", {
  headers: { Authorization: "Bearer " + token }
});
const { data } = await res.json();   // data.items, data.total, ...
```

Postman: `postman/Hospital_Phase02.postman_collection.json` (Login saves the token for receptionist/doctor requests automatically — run "Login (receptionist)" first).
