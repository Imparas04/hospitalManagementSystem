# Testing Guide

## Run tests
From the project root in PowerShell:
```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q
```
Alternatively, activate the virtual environment and run `python -m pytest -q`.

## Previously reported result
A test run during project maintenance reported:
```text
513 passed in 800.98s (0:13:20)
```
This is a historical result, not a guarantee for later changes. Re-run tests to verify the current checkout.

## Manual smoke checks
- Start the backend and confirm it boots without errors.
- Open the frontend in a browser and sign in using a configured development account.
- Check dashboard, patient, doctor, and pharmacy pages with test data.
- Check reports and CSV/Excel/PDF exports.
- Confirm protected routes reject unauthorized requests.
- Inspect browser developer tools and backend logs for failed requests.

When reporting a failure, include the command, error output, and affected endpoint. Remove passwords, tokens, secret keys, and patient-identifying data before sharing logs.
