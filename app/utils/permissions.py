"""Role -> permission map (the single place that defines "who can do what").

Permission names look like  "<module>:<action>".
Admin has "*" (everything). Later phases just USE these names on their routes.
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
        "appointments:read", "appointments:create", "appointments:update",
        "admissions:read", "admissions:create",
    },
    ROLE_DOCTOR: {
        "patients:read", "patients:update",
        "appointments:read", "appointments:update",
        "prescriptions:read", "prescriptions:create",
        "lab:order", "lab:read", "lab:review",
    },
    ROLE_NURSE: {
        "patients:read",
        "vitals:read", "vitals:create",
        "beds:read", "beds:update", "admissions:read",
    },
    ROLE_LAB_TECH: {
        "lab:read", "lab:update", "lab:enter_result",
    },
    ROLE_PHARMACIST: {
        "prescriptions:read", "pharmacy:read", "pharmacy:update", "pharmacy:issue",
    },
    ROLE_BILLING: {
        "billing:read", "billing:create", "billing:update", "payments:create",
    },
}


def has_permission(role_name, permission):
    perms = ROLE_PERMISSIONS.get(role_name, set())
    return "*" in perms or permission in perms
