from flask import Blueprint, current_app, g, request

from app.extensions import db
from app.middleware.auth import login_required
from app.services.auth_service import authenticate, make_token
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_password

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    login_id = data.get("username")
    password = data.get("password")

    errors = {}
    if not isinstance(login_id, str) or not login_id.strip():
        errors["username"] = "Username or email is required"
    if not isinstance(password, str) or not password:
        errors["password"] = "Password is required"
    if errors:
        return error_response("Validation failed", errors, 400)

    user = authenticate(login_id.strip(), password)
    if user is None:
        # Same message for wrong user / wrong password / inactive: do not leak which one.
        return error_response("Invalid username or password", status=401)

    return success_response("Login successful", {
        "access_token": make_token(user),
        "token_type": "Bearer",
        "expires_in_seconds": int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        "user": user.to_dict(),
    })


@bp.get("/me")
@login_required
def me():
    return success_response("Current user", g.current_user.to_dict())


@bp.post("/change-password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old, new = data.get("old_password"), data.get("new_password")
    errors = {}
    if not old or not g.current_user.check_password(old):
        errors["old_password"] = "Old password is incorrect"
    pw_error = validate_password(new)
    if pw_error:
        errors["new_password"] = pw_error
    elif old == new:
        errors["new_password"] = "New password must be different from the old one"
    if errors:
        return error_response("Validation failed", errors, 400)

    g.current_user.set_password(new)
    db.session.commit()
    return success_response("Password changed successfully")
