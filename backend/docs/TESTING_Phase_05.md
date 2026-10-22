# Testing - Phase 5

## Automated tests (pytest)
```bash
pytest -v
```
Expected: **190 passed** (145 from Phases 1-4 + 45 new).

| File | Covered |
|---|---|
| `tests/test_lab.py` (17) | test catalog + RBAC, duplicate code (409), doctor orders test, **order blocked without a doctor profile**, validation + unknown refs, **full workflow ordered -> sample -> processing -> result -> reviewed**, result can't be entered twice, review needs a result, lab tech cannot review, filters/404 |
| `tests/test_pharmacy.py` (28) | medicine CRUD + RBAC + duplicate (409), batch rules (past expiry / bad quantity / duplicate batch), low-stock filter, prescription create/validation/RBAC, **full issue**, **partial issue when stock short**, **FEFO uses earliest-expiring batch first** (later batch added first, still untouched), no re-issue, doctor cannot issue |

## Manual test on real MySQL
1. Import `postman/Hospital_Phase05.postman_collection.json`, run the Logins folder.
2. Make sure the demo doctor has a doctor profile (run the Phase 3 "Create doctor profile" request first).
3. Lab folder, top to bottom: create test -> order -> sample -> processing -> result -> review.
4. Pharmacy folder: create medicine -> add two batches -> prescribe more than you have in stock -> issue -> check `breakdown.shortfall` and `GET /pharmacy/medicines?low_stock=true`.

| # | Test | Expected |
|---|---|---|
| 1 | Receptionist reads `/api/lab/orders` | 403 |
| 2 | Nurse reviews a lab result | 403 |
| 3 | Doctor issues a prescription | 403 |
| 4 | Add batch with a past expiry date | 400 |
| 5 | Prescribe 25, stock is 20 | issue returns `partially_issued`, `shortfall: 5` |
| 6 | Create medicine with an existing name | 409 |
