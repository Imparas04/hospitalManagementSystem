# Testing - Phase 7

## Automated tests (pytest)
```bash
pip install -r requirements.txt     # pandas, numpy, openpyxl, tzdata are new
pytest -v
```
Expected: **513 passed** (249 from Phases 1-6 + 264 new). Tests use in-memory SQLite, so your MySQL data is untouched. Running everything takes about 8 minutes.

| File | Tests | What it proves |
|---|---|---|
| `test_audit.py` | 24 | **every write endpoint has an audit rule** (the test fails if you add a POST/PUT/DELETE without one); login + failed login logged (no password, control characters stripped); user/role/entity/description/IP recorded; rejected requests and plain reads are not logged; entity id from the URL or nested response; the whole patient story is traceable; username/role are snapshots; passwords never appear; **an audit failure never breaks the real request**; admin-only + read-only (405); filters, dates, pagination, validation |
| `test_notifications.py` | 31 | all 5 types reach only the right people; abnormal vs normal severity; low-stock / out-of-stock / expiry (soon, within a week, far away, expired, empty batch); alert **resolves on restock and returns unread when low again**; text updates when a payment is made; age setting; **no duplicates after many refreshes**; read state is **per user**; cannot read someone else's; read-all; filters; a broken notification never stops a discharge |
| `test_dashboard.py` | 102 | every role gets exactly its own cards; cards count real data; cancelled / deactivated / resolved items excluded; a doctor sees only their own patients; **revenue uses the hospital timezone**; all 7 charts: Chart.js shape, equal-length datasets, zero-filled days, no divide-by-zero, **access matrix for every chart x every role**, input validation |
| `test_reports.py` | 103 | all 7 reports x 4 formats work **even on an empty hospital**; hand-checked figures (net billed 2268, shares 62.5 / 66.7 / 33.3 %, stock 16 = 20 - 4); week = Monday-Sunday; late-night IST payment lands on the right day; period validation; CSV (BOM, table choice), Excel (sheets, bold header), PDF (text read back, landscape for wide tables); **spreadsheet formula injection neutralised**; exports audited, JSON views and forbidden attempts are not; access matrix report x role |
| `test_timeutils.py` | 4 | IST day starts 5h30 before UTC midnight; inclusive ranges; month helpers |

## Manual test on real MySQL
1. Rebuild the database (`schema.sql` + `seed.sql`, then `flask create-admin` and `flask seed-demo-users`): Phase 7 adds three tables.
2. Import `postman/Hospital_Phase07.postman_collection.json`, run **Logins**.
3. Build some data using the earlier collections (patient -> appointment -> admission -> lab result -> prescription -> discharge -> bill -> payment).
4. **Dashboards:** call it with each login and compare the numbers (billing sees money, pharmacist sees stock, nurse sees beds).
5. **Notifications:** pharmacist and billing logins should show low stock / expiring / payment pending; doctor should see the lab result.
6. **Audit log:** as admin, filter by `entity_type=Patient&entity_id=1`.
7. **Reports:** run an export request in Postman with *Send and Download* and open the file.

| # | Test | Expected |
|---|---|---|
| 1 | Receptionist calls `/api/audit-logs` | 403 |
| 2 | Billing staff calls `/api/reports/daily` | 403 |
| 3 | Nurse calls `/api/analytics/monthly-revenue` | 403 |
| 4 | Wrong password login | 401, and an `auth.login_failed` entry appears |
| 5 | `?format=docx` on a report | 400 |
| 6 | `POST /api/audit-logs` | 405 |
| 7 | Mark someone else's notification as read | 404 |
