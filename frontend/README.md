# Smart Hospital frontend

A responsive HTML/CSS/JavaScript frontend for the Flask REST API in `../app`. It uses JWT authentication and the API's role-based permissions; the server remains the authority for access control.

## Start locally on Windows

1. Start MySQL and create/configure `hospital_db`.
2. In `../`, create `.env` from `.env.example` and set `DB_USER`, `DB_PASSWORD`, and a long random `JWT_SECRET_KEY`.
3. In a terminal opened in `backend/`:
   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   flask --app run.py init-db
   flask --app run.py create-admin
   python run.py
   ```
   If you have not created a virtual environment yet, run `python -m venv venv` first.
4. Open a second terminal in `backend/frontend/` and run:
   ```powershell
   py -m http.server 8080
   ```
5. Open `http://127.0.0.1:8080` and sign in with the admin credentials created in step 3.

Default API base is `http://127.0.0.1:5000/api`. To change it, open browser DevTools Console and run:
```js
localStorage.setItem('hospital_api_url', 'http://127.0.0.1:5000/api'); location.reload();
```

## Notes
- This frontend deliberately does not use mock data: a successful login and API connection are required.
- Chart.js and Google Fonts are loaded from CDNs; the app's core screens work without the font CDN, but charts require network access to the Chart.js CDN.
- If an endpoint responds with `401`, sign in again. `403` means the logged-in role does not have permission. These are backend security responses, not necessarily server crashes.
- The UI exposes the primary workflows and report exports. Some advanced actions (e.g. doctor schedules, detailed prescription line-item entry, discharge summaries, PDF receipts) are available in the API and API docs but need dedicated UI forms before the frontend can be considered feature-complete.
