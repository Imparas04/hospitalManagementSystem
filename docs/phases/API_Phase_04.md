# API Documentation - Phase 4 (Emergency, Triage & Smart Bed Allocation)

Adds to Phases 1-3. Same conventions as before.

**Permissions:** `triage:create` -> nurse; `triage:read`/`triage:update` -> nurse, doctor (admin always has access).

---

## Record triage (vitals in, priority out)
`POST /api/triage` - Auth: **triage:create**
```json
{
  "patient_id": 1,
  "blood_pressure_systolic": 180, "blood_pressure_diastolic": 100,
  "heart_rate": 140, "oxygen_level": 88, "temperature": 103.5,
  "symptoms": "Chest pain, difficulty breathing",
  "emergency_condition": "Suspected cardiac event",
  "icu_required": true, "isolation_required": false
}
```
`priority_level` (`critical`/`high`/`medium`/`low`) and `priority_score` are **computed automatically** - see "How priority is calculated" below. Response `201`, status starts as `waiting`.

## Emergency queue
`GET /api/triage/queue` - Auth: **triage:read** -> all `waiting` patients, **most urgent first** (highest score, then earliest arrival time as tie-breaker).

## List / get
`GET /api/triage?status=&priority_level=&patient_id=`
`GET /api/triage/<id>`

## Update status
`PUT /api/triage/<id>/status` - Auth: **triage:update** - `{"status": "in_treatment"}` (`waiting`|`bed_assigned`|`in_treatment`|`resolved`)

## Smart bed allocation
`POST /api/triage/<id>/allocate-bed` - Auth: **triage:update**
```json
{"doctor_id": 1}
```
Automatically finds the best available bed (see algorithm below), admits the patient into it (creates an `Admission`, occupies the bed), links it back to the triage record, and sets triage status to `bed_assigned`. `409` if no eligible bed exists; `400` if this triage case isn't `waiting` anymore.

## Resolve
`POST /api/triage/<id>/resolve` -> status `resolved`

---

## How priority is calculated
Each abnormal vital adds points (see `app/services/triage_service.py::calculate_priority` for the exact thresholds and comments): oxygen below 90% or heart rate past 40/130 add the most points; blood pressure and temperature add fewer. Total score maps to a level:

| Score | Priority |
|---|---|
| >= 7 | critical |
| 4-6 | high |
| 2-3 | medium |
| 0-1 | low |

This is a simple, explainable rule-based model (not a real clinical protocol) - good for a demo and easy to extend with more rules later.

## How smart bed allocation works
1. Required bed type: `icu_required` -> `icu` bed; else `isolation_required` -> `isolation` bed; else `general`.
2. Only beds in a ward whose `gender_restriction` is empty (mixed) or matches the patient's gender are considered.
3. Only `available` beds are considered.
4. Among the matches, the bed in the ward with the **fewest currently-free beds** is picked first (keeps larger wards' spare capacity for future patients instead of using it on singles).

Wards now also accept `gender_restriction` (`"male"`/`"female"`, omit for mixed) when created via `POST /api/wards` (Phase 3 endpoint, extended in this phase).
