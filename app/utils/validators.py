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


def validate_patient_payload(data, partial=False):
    """Validate the body for creating (partial=False) or updating (partial=True) a patient."""
    from datetime import date, datetime

    from app.models.patient import BLOOD_GROUP_CHOICES, GENDER_CHOICES

    errors = {}

    def missing(field):
        return not partial and (field not in data or data[field] in (None, ""))

    if missing("full_name"):
        errors["full_name"] = "Full name is required"
    elif "full_name" in data and (not isinstance(data["full_name"], str) or not 2 <= len(data["full_name"].strip()) <= 100):
        errors["full_name"] = "Full name must be 2-100 characters"

    if missing("date_of_birth"):
        errors["date_of_birth"] = "Date of birth is required (format: YYYY-MM-DD)"
    elif "date_of_birth" in data:
        try:
            dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            if dob > date.today():
                errors["date_of_birth"] = "Date of birth cannot be in the future"
            elif dob.year < date.today().year - 130:
                errors["date_of_birth"] = "Date of birth is not realistic"
        except (ValueError, TypeError):
            errors["date_of_birth"] = "Date of birth must be in format YYYY-MM-DD"

    if missing("gender"):
        errors["gender"] = "Gender is required"
    elif "gender" in data and data["gender"] not in GENDER_CHOICES:
        errors["gender"] = f"Gender must be one of: {', '.join(GENDER_CHOICES)}"

    if "blood_group" in data and data["blood_group"] not in (None, "") and data["blood_group"] not in BLOOD_GROUP_CHOICES:
        errors["blood_group"] = f"Blood group must be one of: {', '.join(BLOOD_GROUP_CHOICES)}"

    if missing("phone"):
        errors["phone"] = "Phone is required"
    elif "phone" in data and (not isinstance(data["phone"], str) or not PHONE_RE.match(data["phone"])):
        errors["phone"] = "Phone must be 7-15 digits (optional leading +)"

    if data.get("email") not in (None, ""):
        if not isinstance(data["email"], str) or not EMAIL_RE.match(data["email"]):
            errors["email"] = "Enter a valid email address"

    if data.get("emergency_contact_phone") not in (None, ""):
        if not PHONE_RE.match(data["emergency_contact_phone"]):
            errors["emergency_contact_phone"] = "Emergency contact phone must be 7-15 digits (optional leading +)"

    if "is_emergency_registration" in data and not isinstance(data["is_emergency_registration"], bool):
        errors["is_emergency_registration"] = "is_emergency_registration must be true or false"

    return errors


def validate_medical_history_payload(data):
    errors = {}
    valid_types = ("allergy", "chronic_condition", "surgery", "note")
    if data.get("condition_type") not in valid_types:
        errors["condition_type"] = f"condition_type must be one of: {', '.join(valid_types)}"
    desc = data.get("description")
    if not isinstance(desc, str) or not 2 <= len(desc.strip()) <= 500:
        errors["description"] = "description is required (2-500 characters)"
    return errors


def validate_visit_payload(data):
    errors = {}
    valid_types = ("opd", "emergency", "follow_up")
    if data.get("visit_type") not in valid_types:
        errors["visit_type"] = f"visit_type must be one of: {', '.join(valid_types)}"
    reason = data.get("reason")
    if not isinstance(reason, str) or not 2 <= len(reason.strip()) <= 255:
        errors["reason"] = "reason is required (2-255 characters)"
    return errors


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
