"""Small, readable input validation helpers.

Each validator returns a dict of {field: error_message}. Empty dict = valid.
"""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,50}$")
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def validate_password(password):
    """Min 8 chars, at least one letter and one digit. Returns error text or None."""
    if not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password is too long (max 128 characters)"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Password must contain at least one letter and one digit"
    return None


def validate_user_payload(data, valid_roles, partial=False):
    """Validate the body for creating (partial=False) or updating (partial=True) a user."""
    errors = {}

    def missing(field):
        return not partial and (field not in data or data[field] in (None, ""))

    # username
    if missing("username"):
        errors["username"] = "Username is required"
    elif "username" in data and not USERNAME_RE.match(str(data["username"])):
        errors["username"] = "Username must be 3-50 characters: letters, digits, '_' or '.'"

    # email
    if missing("email"):
        errors["email"] = "Email is required"
    elif "email" in data and (not isinstance(data["email"], str) or not EMAIL_RE.match(data["email"])):
        errors["email"] = "Enter a valid email address"

    # full name
    if missing("full_name"):
        errors["full_name"] = "Full name is required"
    elif "full_name" in data and (not isinstance(data["full_name"], str) or not 2 <= len(data["full_name"].strip()) <= 100):
        errors["full_name"] = "Full name must be 2-100 characters"

    # role
    if missing("role"):
        errors["role"] = "Role is required"
    elif "role" in data and data["role"] not in valid_roles:
        errors["role"] = f"Role must be one of: {', '.join(valid_roles)}"

    # phone (optional)
    if data.get("phone") not in (None, ""):
        if not isinstance(data["phone"], str) or not PHONE_RE.match(data["phone"]):
            errors["phone"] = "Phone must be 7-15 digits (optional leading +)"

    # password (only when creating)
    if not partial:
        pw_error = validate_password(data.get("password"))
        if pw_error:
            errors["password"] = pw_error

    return errors
