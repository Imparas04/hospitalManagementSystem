# Testing - Phase 1

## A. Automated tests (pytest)
Tests use an **in-memory SQLite database**, so they never touch your MySQL data.
```bash
pytest -v
```
Expected: all tests pass (31). Covered:

| Area | Cases |
|---|---|
| Success | login (username + email), me, create/list/get/update user, change/reset password |
| Invalid input | missing fields, bad email/username/password/role, empty body, bad page number |
| Unauthorized | no token, garbage token -> `401` |
| Wrong role | all 6 non-admin roles get `403` on admin APIs |
| Edge cases | duplicate username/email (`409`), admin cannot lock self out, deactivated user's old token stops working, SQL-injection style login, unknown URL returns JSON 404 |

## B. Manual test on real MySQL (Postman or curl)
1. Setup steps from README (DB + `flask create-admin` + `python run.py`).
2. Import `postman/Hospital_Phase01.postman_collection.json`.
3. Run **Login (admin)** -> token is saved automatically.
4. Try **Create user**, **List users**, then log in as that user and call **List users** again -> must return `403`.
5. Call any protected API without a token -> `401`.

| # | Test | Expected |
|---|---|---|
| 1 | GET /api/health | 200 |
| 2 | Login correct | 200 + token |
| 3 | Login wrong password | 401 |
| 4 | GET /api/users without token | 401 |
| 5 | GET /api/users as doctor | 403 |
| 6 | POST /api/users as admin, valid | 201 |
| 7 | Same POST again | 409 |
| 8 | POST /api/users with weak password | 400 |
| 9 | DELETE own admin account | 400 |
