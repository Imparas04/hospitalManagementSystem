# Smart Hospital Management System — Project Overview

## Purpose
A web-based project intended to support common hospital workflows through a dashboard and modular backend API.

## Functional areas
The backend structure includes patient records, doctors and departments, appointments, admissions, discharge, beds, billing, pharmacy and medicine stock, emergency triage, laboratory workflows, notifications, dashboard analytics, reports, users, authentication, permissions, and audit records.

The reporting work includes daily, weekly, monthly, department-wise, doctor-performance, revenue, and pharmacy reports, with CSV, Excel, and PDF export functionality.

## Technology
- Backend: Python and Flask
- Data/model layer: SQLAlchemy-based model modules
- Reporting: Pandas-based report builders/exporters
- Frontend: HTML, CSS, and JavaScript
- API prefix: `/api`

Confirm exact dependency versions and database configuration in `backend/requirements.txt` and the local environment.

## Repository layout
```text
hospitalManagementSystem/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── routes/
│   │   └── services/
│   ├── tests/
│   ├── docs/
│   ├── postman/
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
├── README.md
└── docs/
```

## Production note
This is a development project. Review security, privacy, access controls, deployment configuration, and applicable healthcare requirements before using real patient information or deploying in a hospital.
