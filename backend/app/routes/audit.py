"""Audit log viewer - ADMIN ONLY, read-only. There is intentionally no way to edit or delete entries."""
from datetime import datetime

from flask import Blueprint, request

from app.extensions import db
from app.middleware.auth import roles_required
from app.models.audit import AuditLog
from app.models.role import ROLE_ADMIN
from app.utils.responses import error_response, success_response
from app.utils.timeutils import range_bounds_utc

bp = Blueprint("audit", __name__, url_prefix="/api/audit-logs")


def _parse_date(name, errors):
    value = request.args.get(name)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        errors[name] = f"{name} must be in format YYYY-MM-DD"
        return None


@bp.get("")
@roles_required(ROLE_ADMIN)
def list_logs():
    """Query: user_id, username, role, action, entity_type, entity_id, q (search description),
    date_from, date_to (local dates, YYYY-MM-DD), page, per_page. Newest first.
    Example - full history of one patient:  ?entity_type=Patient&entity_id=5"""
    errors = {}
    date_from, date_to = _parse_date("date_from", errors), _parse_date("date_to", errors)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    if page < 1 or per_page < 1:
        errors["page"] = "page and per_page must be positive numbers"
    for name in ("user_id", "entity_id"):
        if request.args.get(name) and not request.args[name].isdigit():
            errors[name] = f"{name} must be a whole number"
    if errors:
        return error_response("Validation failed", errors, 400)

    q = AuditLog.query
    a = request.args
    if a.get("user_id"):
        q = q.filter(AuditLog.user_id == int(a["user_id"]))
    if a.get("username"):
        q = q.filter(AuditLog.username == a["username"])
    for field in ("role", "action", "entity_type"):
        if a.get(field):
            q = q.filter(getattr(AuditLog, field) == a[field])
    if a.get("entity_id"):
        q = q.filter(AuditLog.entity_id == int(a["entity_id"]))
    if a.get("q"):
        q = q.filter(AuditLog.description.like(f"%{a['q']}%"))
    if date_from:
        q = q.filter(AuditLog.created_at >= range_bounds_utc(date_from, date_from)[0])
    if date_to:
        q = q.filter(AuditLog.created_at < range_bounds_utc(date_to, date_to)[1])

    result = q.order_by(AuditLog.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return success_response("Audit logs fetched", {
        "items": [l.to_dict() for l in result.items], "page": result.page, "per_page": result.per_page,
        "total": result.total, "pages": result.pages})


@bp.get("/actions")
@roles_required(ROLE_ADMIN)
def list_actions():
    """Distinct action names, for a filter drop-down."""
    rows = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    return success_response("Actions fetched", [r[0] for r in rows])
