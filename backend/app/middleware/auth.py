"""Authentication + authorization decorators (RBAC enforced on the server).

Usage on a route:

    @bp.get("/something")
    @roles_required("admin")              # only these roles
    def ...

    @bp.post("/patients")
    @permission_required("patients:create")   # any role that has this permission
    def ...

    @bp.get("/me")
    @login_required                       # any logged-in, active user
    def ...

Flow: check JWT -> load user from DB -> user must exist and be active ->
check role/permission. Because we load the user from the DB on every request,
deactivating a user or changing their role takes effect immediately.
"""
from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db
from app.models.user import User
from app.utils.permissions import has_permission
from app.utils.responses import error_response


def _load_current_user():
    """Validate the JWT and put the user in `g.current_user`. Returns an error tuple or None."""
    verify_jwt_in_request()  # raises -> handled in error_handlers.py (401)
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None or not user.is_active:
        return error_response("Account not found or deactivated", status=401)
    g.current_user = user
    return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        error = _load_current_user()
        if error:
            return error
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            error = _load_current_user()
            if error:
                return error
            if g.current_user.role.name not in allowed_roles:
                return error_response("You do not have permission to perform this action", status=403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            error = _load_current_user()
            if error:
                return error
            if not has_permission(g.current_user.role.name, permission):
                return error_response("You do not have permission to perform this action", status=403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
