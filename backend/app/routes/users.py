"""User management - ADMIN ONLY (create staff accounts, change roles, deactivate)."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import roles_required
from app.models.role import ALL_ROLES, ROLE_ADMIN, Role
from app.models.user import User
from app.services import user_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_password, validate_user_payload

bp = Blueprint("users", __name__, url_prefix="/api")


@bp.get("/roles")
@roles_required(ROLE_ADMIN)
def list_roles():
    roles = Role.query.order_by(Role.id).all()
    return success_response("Roles fetched", [r.to_dict() for r in roles])


@bp.post("/users")
@roles_required(ROLE_ADMIN)
def create_user():
    data = request.get_json(silent=True) or {}
    errors = validate_user_payload(data, ALL_ROLES)
    if not errors:
        errors = user_service.username_or_email_taken(data["username"], data["email"])
        if errors:
            return error_response("User already exists", errors, 409)
    else:
        return error_response("Validation failed", errors, 400)

    user = user_service.create_user(data)
    return success_response("User created successfully", user.to_dict(), 201)


@bp.get("/users")
@roles_required(ROLE_ADMIN)
def list_users():
    """Query params: role, is_active (true/false), q (search name/username/email), page, per_page."""
    query = User.query.join(Role)
    role = request.args.get("role")
    if role:
        query = query.filter(Role.name == role)
    is_active = request.args.get("is_active")
    if is_active in ("true", "false"):
        query = query.filter(User.is_active == (is_active == "true"))
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.full_name.like(like), User.username.like(like), User.email.like(like)))

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)
    if page < 1 or per_page < 1:
        return error_response("page and per_page must be positive numbers", status=400)

    result = query.order_by(User.id).paginate(page=page, per_page=per_page, error_out=False)
    return success_response("Users fetched", {
        "items": [u.to_dict() for u in result.items],
        "page": result.page,
        "per_page": result.per_page,
        "total": result.total,
        "pages": result.pages,
    })


@bp.get("/users/<int:user_id>")
@roles_required(ROLE_ADMIN)
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response("User not found", status=404)
    return success_response("User fetched", user.to_dict())


@bp.put("/users/<int:user_id>")
@roles_required(ROLE_ADMIN)
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response("User not found", status=404)

    data = request.get_json(silent=True) or {}
    if not data:
        return error_response("Validation failed", {"body": "No data provided"}, 400)
    errors = validate_user_payload(data, ALL_ROLES, partial=True)
    if "is_active" in data and not isinstance(data["is_active"], bool):
        errors["is_active"] = "is_active must be true or false"
    if errors:
        return error_response("Validation failed", errors, 400)

    # Safety: an admin must not lock themselves out.
    if user.id == g.current_user.id and (data.get("is_active") is False or data.get("role", ROLE_ADMIN) != ROLE_ADMIN):
        return error_response("You cannot deactivate or change the role of your own account", status=400)

    dup = user_service.username_or_email_taken(data.get("username"), data.get("email"), exclude_id=user.id)
    if dup:
        return error_response("User already exists", dup, 409)

    user = user_service.update_user(user, data)
    return success_response("User updated successfully", user.to_dict())


@bp.delete("/users/<int:user_id>")
@roles_required(ROLE_ADMIN)
def deactivate_user(user_id):
    """Soft delete: we never remove users because later tables (audit logs, bills...) refer to them."""
    user = db.session.get(User, user_id)
    if not user:
        return error_response("User not found", status=404)
    if user.id == g.current_user.id:
        return error_response("You cannot deactivate your own account", status=400)
    user.is_active = False
    db.session.commit()
    return success_response("User deactivated successfully", user.to_dict())


@bp.post("/users/<int:user_id>/reset-password")
@roles_required(ROLE_ADMIN)
def reset_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response("User not found", status=404)
    new_password = (request.get_json(silent=True) or {}).get("new_password")
    pw_error = validate_password(new_password)
    if pw_error:
        return error_response("Validation failed", {"new_password": pw_error}, 400)
    user.set_password(new_password)
    db.session.commit()
    return success_response("Password reset successfully")
