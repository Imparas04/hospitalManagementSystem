# Testing - Phase 6

## Automated tests (pytest)
```bash
pytest -v
```
Expected: **249 passed** (190 from Phases 1-5 + 59 new).

| File | Covered |
|---|---|
| `tests/test_billing.py` (33) | preview saves nothing; bill adds consultation + bed + lab + medicine correctly (2400.00); **discount is applied before tax** (2268.00); **rounding to 2 decimals** (91.86 case); **nothing billed twice**; bill by patient code; **bed charge waits for discharge** and **counts every started day** (2.5 days -> 3); **medicine billed in rounds** (only the newly issued quantity); unissued medicine / unfinished lab not billed; validation; add services; adjust discount/tax (blocked after a payment); **partial payments with different methods**; overpay and pay-on-paid rejected; receipts show balance after *that* payment; outstanding list; filters; unique increasing numbers; RBAC for 5 roles + no token; invoice and receipt PDFs (content checked); PDF with `<b>`/`&` in text |
| `tests/test_discharge.py` (26) | full summary (patient, doctor, labs, medicines, final bill); **bed freed**; exactly one final bill; works after a nurse already discharged; no double discharge (409); validation (past / badly formatted follow-up date); optional fields; write = doctor/admin only; read = doctor/nurse/receptionist/billing/admin only; live payment status; PDF contains every section; special characters |

Every PDF test extracts the text back out of the PDF (with `pypdf`) and checks the real content.

## Manual test on real MySQL
1. Run the Phase 1-5 setup, then import `postman/Hospital_Phase06.postman_collection.json` and run the logins.
2. Build a patient story first (appointment completed, admission, lab result, issued medicine) using the earlier Postman collections.
3. **Discharge** request -> note the final bill number in the response.
4. **Adjust** the bill (10% discount) -> **Pay part by cash** -> **Pay the rest by UPI**.
5. Open the three PDF requests (in Postman use *Send and Download*).

| # | Test | Expected |
|---|---|---|
| 1 | Preview while patient is still admitted | no `bed` line |
| 2 | Generate a bill twice | 2nd call: 409 |
| 3 | Pay more than the outstanding amount | 400 |
| 4 | Change discount after a payment | 400 |
| 5 | Receptionist opens `/api/bills` | 403 |
| 6 | Nurse writes a discharge summary | 403 |
| 7 | Pharmacist reads a discharge summary | 403 |
