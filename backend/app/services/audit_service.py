"""Writes one row to the audit log. Used by the audit middleware (app/middleware/audit.py)."""
from flask import has_request_context, request

from app.extensions import db
from app.models.audit import AuditLog


def record(action, description, user=None, user_id=None, username=None, role=None,
           entity_type=None, entity_id=None):
    """Pass either a `user` object, or user_id/username/role explicitly (failed logins have no user)."""
    if user is not None:
        user_id, username, role = user.id, user.username, user.role.name
    entry = AuditLog(
        user_id=user_id, username=username, role=role, action=action, entity_type=entity_type,
        entity_id=entity_id, description=(description or "")[:500],
        ip_address=request.remote_addr if has_request_context() else None,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
