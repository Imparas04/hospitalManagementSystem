"""Role -> permission map (the single place that defines "who can do what").

Permission names look like  "<module>:<action>".
Admin has "*" (everything), which includes the audit log and every report.
Dashboards (GET /api/dashboard) are open to every logged-in role but return role-specific numbers. Later phases just USE these names on their routes.
To change what a role can do, edit only this file.
"""
from app.models.role import (
    ROLE_ADMIN, ROLE_BILLING, ROLE_DOCTOR, ROLE_LAB_TECH,
    ROLE_NURSE, ROLE_PHARMACIST, ROLE_RECEPTIONIST,
)

ROLE_PERMISSIONS = {
    ROLE_ADMIN: {"*"},
    ROLE_RECEPTIONIST: {
        "patients:read", "patients:create", "patients:update",
        "doctors:read", "departments:read",
        "appointments:read", "appointments:create", "appointments:update",
        "wards:read", "beds:read",
        "admissions:read", "admissions:create", "admissions:update",
        "discharge:read",
        "analytics:registrations", "analytics:departments", "analytics:beds",
    },
    ROLE_DOCTOR: {
        "patients:read", "patients:update",
        "doctors:read", "departments:read",
        "appointments:read", "appointments:update",
        "wards:read", "beds:read", "admissions:read",
        "prescriptions:read", "prescriptions:create",
        "lab:order", "lab:read", "lab:review",
        "triage:read", "triage:update",
        "discharge:create", "discharge:read",
        "analytics:departments", "analytics:emergency", "analytics:lab",
    },
    ROLE_NURSE: {
        "patients:read",
        "doctors:read", "departments:read",
        "appointments:read",
        "vitals:read", "vitals:create",
        "wards:read", "beds:read", "beds:update",
        "admissions:read", "admissions:update",
        "triage:read", "triage:create", "triage:update",
        "discharge:read",
        "analytics:beds", "analytics:emergency",
    },
    ROLE_LAB_TECH: {
        "lab:read", "lab:update", "lab:enter_result",
        "analytics:lab",
    },
    ROLE_PHARMACIST: {
        "prescriptions:read", "pharmacy:read", "pharmacy:update", "pharmacy:issue",
        "analytics:medicine", "reports:pharmacy",
    },
    ROLE_BILLING: {
        "billing:read", "billing:create", "billing:update", "payments:create",
        "discharge:read",
        "analytics:revenue", "reports:revenue",
    },
}


def has_permission(role_name, permission):
    perms = ROLE_PERMISSIONS.get(role_name, set())
    return "*" in perms or permission in perms
