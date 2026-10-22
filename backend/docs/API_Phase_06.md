# API Documentation - Phase 6 (Billing, Payments, Discharge, PDF)

Adds to Phases 1-5. Same conventions: JSON body, `Authorization: Bearer <token>`, same success/error shape. Money is in **Rupees**, returned as numbers with 2 decimals (e.g. `2397.94`).

**Permissions** (admin always has access):

| Action | Roles |
|---|---|
| Billing (`/api/bills*`, `/api/payments*`) | billing_staff |
| Write a discharge summary (`discharge:create`) | doctor |
| Read a discharge summary / PDF (`discharge:read`) | doctor, nurse, receptionist, billing_staff |

---

## !! Important for the frontend: opening PDFs
PDF endpoints need the JWT header, so a plain `<a href="...">` or `window.open(url)` will get **401**. Fetch it with the header and show the blob:
```js
async function openPdf(path) {
  const res = await fetch("http://localhost:5000/api" + path, {
    headers: { Authorization: "Bearer " + localStorage.getItem("token") }
  });
  if (!res.ok) { alert((await res.json()).message); return; }   // errors are JSON, success is a PDF
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");            // or set it as an <iframe>/<embed> src
}
openPdf("/bills/5/pdf");
```

## New price fields on earlier APIs (all optional, have defaults)
| Where | Field | Default |
|---|---|---|
| `POST/PUT /api/doctors` | `consultation_fee` | 500 |
| `POST /api/wards` | `daily_charge` (per day) | 1000 |
| `POST /api/lab/tests` | `price` | 300 |
| `POST /api/pharmacy/medicines` | `unit_price` | 10 |

They are also returned in the matching GET responses. Numbers must be `>= 0` with at most 2 decimals.

---

# BILLING

## How the automatic bill is calculated
```
  Consultation   completed appointments            x doctor's consultation_fee
+ Bed / room     discharged stays: days x           ward's daily_charge   (every started day counts)
+ Laboratory     tests with a result entered        x test price
+ Medicine       quantity actually ISSUED           x medicine unit_price
+ Other services typed in by billing staff
= Subtotal
- Discount       subtotal x discount %
+ Tax            (subtotal - discount) x tax %
= TOTAL
```
Safe by design: each service is billed **once only** (the database blocks duplicates), medicines are billed only for what the pharmacy actually issued (partial issues are billed in rounds), and bed charges appear only after discharge, when the real number of days is known. Example: 2400.00 - 10% = 2160.00, + 5% tax = 108.00, total **2268.00**.

## Preview (nothing saved)
`GET /api/bills/preview?patient_id=1` or `?patient_code=P2026000001` -> `{items: [...], subtotal}`

## Generate a bill
`POST /api/bills` - Auth: **billing:create**
```json
{
  "patient_code": "P2026000001",
  "discount_percent": 10,
  "tax_percent": 5,
  "other_services": [{"description": "Ambulance", "quantity": 1, "unit_price": 800}]
}
```
Identify the patient with `patient_id` **or** `patient_code`. Everything except the patient is optional (`tax_percent` defaults to the server's `DEFAULT_TAX_PERCENT`, normally 0). Response `201`: the bill with `items` and `payments` arrays.
Errors: `400` validation, `404` patient not found, `409` "Nothing to bill - this patient has no unbilled services".

Bill fields: `bill_number` (e.g. `B2026000001`), `subtotal`, `discount_percent`, `discount_amount`, `tax_percent`, `tax_amount`, `total_amount`, `amount_paid`, `outstanding_amount`, `status` (`unpaid` | `partially_paid` | `paid`).

## List, outstanding, detail
`GET /api/bills?patient_id=&patient_code=&status=&page=&per_page=` -> paginated
`GET /api/bills/outstanding` -> `{total_outstanding, count, bills: [...]}` (everything still unpaid, oldest first)
`GET /api/bills/<id>` -> bill with `items` and `payments`

## Add a service / change discount or tax
`POST /api/bills/<id>/items` - Auth: **billing:update** - `{"description": "Dressing kit", "quantity": 2, "unit_price": 75}` -> `201`. `400` if the bill is already fully paid.
`PUT /api/bills/<id>/adjust` - Auth: **billing:update** - `{"discount_percent": 10, "tax_percent": 5}`. `400` once any payment has been received (so receipts never become wrong).

## Invoice PDF
`GET /api/bills/<id>/pdf` - Auth: **billing:read** -> `application/pdf`

---

# PAYMENTS

## Take a payment
`POST /api/bills/<id>/payments` - Auth: **payments:create**
```json
{"amount": 1000, "method": "cash", "reference": "optional card slip / UPI id"}
```
`method`: `cash` | `card` | `upi` | `bank_transfer` | `insurance`. Partial payments are fine; use a different method for each one if needed.
Response `201`: `{"payment": {..., "receipt_number": "R2026000001"}, "bill": {...updated bill...}}`
Errors: `400` for invalid amount/method, **more than the outstanding balance**, or a bill that is already fully paid; `404` unknown bill.

## Receipts
`GET /api/payments/<id>/receipt` -> JSON incl. `balance_after_payment` (the balance right after *that* payment)
`GET /api/payments/<id>/receipt/pdf` -> PDF

---

# DISCHARGE

## Discharge a patient with a summary
`POST /api/discharge/<admission_id>` - Auth: **discharge:create** (doctor)
```json
{
  "diagnosis": "Community-acquired pneumonia",
  "treatment_summary": "IV antibiotics for 3 days, oxygen support.",
  "doctor_instructions": "Complete the antibiotic course.",
  "follow_up_date": "2026-11-15"
}
```
`diagnosis` and `treatment_summary` are required; `follow_up_date` (`YYYY-MM-DD`, not in the past) and `doctor_instructions` are optional.

In **one call** this: discharges the patient and **frees the bed** (if still admitted), saves the summary, and **generates the final bill** for everything not billed yet. It also works if a nurse already discharged the patient with Phase 3's `POST /api/admissions/<id>/discharge`.
Errors: `400` validation, `404` admission not found, `409` summary already exists.

## Read it
`GET /api/discharge/<admission_id>` - Auth: **discharge:read**. Response `data`:
```json
{
  "admission_id": 1,
  "patient":   {"patient_code": "...", "full_name": "...", "age": 41, "gender": "...", "blood_group": "...", "phone": "..."},
  "doctor":    {"full_name": "...", "specialization": "...", "department": "..."},
  "admission": {"ward": "...", "bed_number": "...", "reason": "...", "admission_date": "...", "discharge_date": "..."},
  "diagnosis": "...", "treatment_summary": "...",
  "lab_reports": [{"test": "...", "code": "CBC", "result": "...", "is_abnormal": true, "reviewer_notes": "..."}],
  "medicines":   [{"medicine": "...", "dosage": "...", "quantity_prescribed": 15, "quantity_issued": 15}],
  "doctor_instructions": "...", "follow_up_date": "2026-11-15",
  "final_bill": {"bill_number": "...", "total_amount": 2397.94, "status": "paid", "items": [...], "payments": [...]}
}
```
Lab reports and medicines are those ordered during the stay. `final_bill` is always live, so it shows the current payment status. `404` until the summary is written.

`GET /api/discharge/<admission_id>/pdf` -> printable discharge summary (`application/pdf`).

---

## Typical flow
1. Doctor: `POST /api/discharge/<admission_id>` -> patient leaves, final bill is created.
2. Billing: `GET /api/bills?patient_code=...` -> optionally `PUT /bills/<id>/adjust` for a discount.
3. Billing: `POST /api/bills/<id>/payments` (one or more) -> `GET /api/payments/<id>/receipt/pdf`.
4. Anyone with access: `GET /api/discharge/<admission_id>/pdf`.

Postman: `postman/Hospital_Phase06.postman_collection.json`.
