from flask import Blueprint, current_app, g, request
from flask_jwt_extended import get_jwt

from app.extensions import db
from app.middleware.auth import login_required
from app.services.auth_service import authenticate, make_token
from app.utils import token_blocklist
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

    # Too many wrong passwords recently? Make the person wait (brute-force protection).
    guard = current_app.extensions["login_guard"]
    key = (login_id.strip().lower(), request.remote_addr)
    wait = guard.seconds_until_allowed(key)
    if wait:
        response, status = error_response(
            f"Too many failed login attempts. Please try again in {-(-wait // 60)} minute(s).", status=429)
        response.headers["Retry-After"] = str(wait)
        return response, status

    user = authenticate(login_id.strip(), password)
    if user is None:
        guard.record_failure(key)
        # Same message for wrong user / wrong password / inactive: do not leak which one.
        return error_response("Invalid username or password", status=401)
    guard.reset(key)

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


@bp.post("/logout")
@login_required
def logout():
    """Make the current token useless right now (it can no longer be used even before it expires)."""
    claims = get_jwt()
    token_blocklist.revoke(claims["jti"], claims["exp"])
    return success_response("Logged out")
