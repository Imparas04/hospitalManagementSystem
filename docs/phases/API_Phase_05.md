# API Documentation - Phase 5 (Laboratory & Pharmacy)

Adds to Phases 1-4. Same conventions: JSON body, `Authorization: Bearer <token>`, same success/error shape and status codes (`409` for duplicates).

**Permissions** (admin always has access):

| Action | Roles |
|---|---|
| Create lab test type / medicine | admin, lab_technician (tests) / admin, pharmacist (medicines) |
| Order a lab test (`lab:order`) | doctor |
| Read lab tests/orders (`lab:read`) | doctor, lab_technician |
| Move order status (`lab:update`) | lab_technician |
| Enter result (`lab:enter_result`) | lab_technician |
| Review result (`lab:review`) | doctor |
| Read medicines (`pharmacy:read`) | pharmacist |
| Add stock batch (`pharmacy:update`) | pharmacist |
| Create prescription (`prescriptions:create`) | doctor |
| Read prescriptions (`prescriptions:read`) | doctor, pharmacist |
| Issue prescription (`pharmacy:issue`) | pharmacist |

> Ordering a test or writing a prescription requires the logged-in doctor to have a **doctor profile** (Phase 3 `POST /api/doctors`). Without one you get `400 "Your account has no linked doctor profile"`.

---

# LABORATORY

Workflow: **ordered -> sample_collected -> processing -> result_entered -> reviewed**

## Test catalog
`POST /api/lab/tests` (admin, lab_technician)
```json
{"name": "Complete Blood Count", "code": "CBC", "normal_range": "4.5-11.0 x10^9/L"}
```
`code` is stored upper-case and must be unique (`409` if it exists).
`GET /api/lab/tests` -> active test types.

## Order a test
`POST /api/lab/orders` (doctor)
```json
{"patient_id": 1, "lab_test_id": 1, "notes": "Fasting sample"}
```
`GET /api/lab/orders?patient_id=&doctor_id=&status=` / `GET /api/lab/orders/<id>` - each order includes patient, doctor, test info and the `result` (null until entered).

## Lab technician steps
`PUT /api/lab/orders/<id>/status` (lab_technician) - `{"status": "sample_collected"}` then `{"status": "processing"}`. Blocked (`400`) once a result exists.

`POST /api/lab/orders/<id>/result` (lab_technician)
```json
{"result_value": "WBC 12.8 x10^9/L - elevated", "is_abnormal": true}
```
Sets status to `result_entered`. `400` if a result was already entered.

## Doctor review
`POST /api/lab/orders/<id>/review` (doctor) - `{"reviewer_notes": "Start antibiotics"}` (optional). Sets status `reviewed`. `400` if no result exists yet or it was already reviewed.

---

# PHARMACY

## Medicine catalog and stock
`POST /api/pharmacy/medicines` (admin, pharmacist)
```json
{"name": "Amoxicillin", "unit": "tablet", "reorder_level": 15}
```
`unit`: `tablet`|`syrup`|`injection`|`ointment`|`drops`. `reorder_level`: total stock below this triggers the low-stock flag. Duplicate name -> `409`.

`GET /api/pharmacy/medicines?q=&low_stock=true` - every medicine includes `total_available` (**non-expired stock only**) and `is_low_stock`. This is the **low-stock alert** feed (the notification system that pushes it to users arrives in Phase 7).

`GET /api/pharmacy/medicines/<id>` - adds the `batches` list (each with `expiry_date`, `available_quantity`, `is_expired`).

`POST /api/pharmacy/medicines/<id>/batches` (pharmacist)
```json
{"batch_number": "B-2026-01", "expiry_date": "2027-12-31", "purchase_quantity": 100}
```
`expiry_date` must be in the future; `batch_number` must be unique per medicine. `available_quantity` starts equal to `purchase_quantity`.

## Prescriptions
`POST /api/prescriptions` (doctor)
```json
{
  "patient_id": 1,
  "notes": "Take after food",
  "items": [
    {"medicine_id": 1, "dosage": "1 tablet three times a day", "quantity": 15}
  ]
}
```
`GET /api/prescriptions?patient_id=&doctor_id=&status=` / `GET /api/prescriptions/<id>` (doctor, pharmacist). Status: `pending` -> `partially_issued` -> `issued`.

## Issue a prescription
`POST /api/prescriptions/<id>/issue` (pharmacist)

Response `200`:
```json
{
  "prescription": { "...": "...", "status": "partially_issued" },
  "breakdown": [
    {"medicine": "Amoxicillin", "issued_now": 20, "shortfall": 5, "reason": "insufficient non-expired stock"}
  ]
}
```
A pharmacist can call it again later after restocking - it only issues what is still outstanding. `400` once fully issued.

### How issuing works (FEFO algorithm)
- **What:** picks which batch each tablet comes from.
- **Why:** hospitals must use the batch that expires first, and must never dispense expired medicine.
- **How:** for each item -> take batches with stock and `expiry_date >= today` -> sort by expiry, earliest first -> take from the first batch, then the next, until the quantity is met or stock runs out. Expired batches are never touched.
- **Example:** batch EARLY (exp Mar 2027, 10 units) and LATE (exp Jun 2028, 10 units); prescription for 14 -> 10 from EARLY, 4 from LATE.

Postman: `postman/Hospital_Phase05.postman_collection.json`.
