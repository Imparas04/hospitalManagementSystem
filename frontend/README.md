# Frontend

Plain HTML + CSS + JavaScript (no build step). Serve this folder with any static server:
```powershell
cd frontend
py -m http.server 8080        # then open http://127.0.0.1:8080
```
The API address is in `js/config.js` (default `http://127.0.0.1:5000/api`).

| File | What it does |
|---|---|
| `index.html` | login screen, app shell, the one shared pop-up dialog |
| `css/style.css` | look and feel (colours, layout, tables, dialogs) |
| `js/config.js` | API address |
| `js/api.js` | talks to the backend, adds the login token, turns errors into readable messages |
| `js/ui.js` | formatting, toast, dialog, **form builder**, table + list builder |
| `js/pages-core.js` | who is logged in, page registry, dropdown loaders, slot picker |
| `js/pages-clinical.js` | patients, departments, doctors, appointments, emergency, wards & beds, admissions |
| `js/pages-services.js` | laboratory, pharmacy, prescriptions, billing |
| `js/pages-admin.js` | dashboard, reports, notifications, users, audit log |
| `js/main.js` | menu, switching pages, login / logout, change password |

### How to add a new page (viva-friendly)
1. In a `pages-*.js` file call `definePage('myPage', {title, group, icon, roles: [...], render: () => renderList({...})})`.
2. Add `'myPage'` to `PAGE_ORDER` in `main.js`.
`renderList` needs: `load` (fetch the rows), `columns`, optional `rowActions` (buttons per row), `buttons` (toolbar) and `filters`.
Forms: `openForm({title, fields:[{name,label,type,required}], onSubmit: async values => {...}})`.

The menu hides pages a role cannot use, but the **server is the real gatekeeper** — never rely on hiding buttons for security.
