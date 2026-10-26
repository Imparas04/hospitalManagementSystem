# Testing - Phase 4

## Automated tests (pytest)
```bash
pytest -v
```
Expected: **145 passed** (127 from Phases 1-3 + 18 new, in `tests/test_triage.py`).

Covered: priority calculation (low and critical cases checked against known scores), validation, RBAC (only nurse/admin create triage; doctor can read/update but not create), emergency queue ordering (critical arriving second still comes first), status transitions, smart bed allocation picking the correct bed TYPE (ICU vs general), allocation correctly failing when no matching bed type exists, **gender-restricted ward correctly rejecting a non-matching patient**, missing `doctor_id` rejected, and double-allocation blocked.

## Quick manual check
1. `POST /api/triage` with abnormal vitals (e.g. oxygen 85, heart rate 150) as nurse -> confirm `priority_level: "critical"`.
2. `GET /api/triage/queue` -> confirm it's sorted most-urgent-first.
3. Create an ICU ward + bed (`POST /api/wards` with `ward_type: "icu"`, then `POST /api/wards/<id>/beds` with `bed_type: "icu"`).
4. `POST /api/triage` with `icu_required: true`, then `POST /api/triage/<id>/allocate-bed` with a doctor_id -> confirm it picks the ICU bed, not a general one.
5. Repeat allocation on the same triage id -> expect `400` (already allocated).
